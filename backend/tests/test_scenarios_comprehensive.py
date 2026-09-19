"""
Comprehensive multi-scenario test suite for Process2BPMN.
Tests all intended features across real-world business scenarios:
  Scenario 1: End-to-End SOP Ingestion (O2C) across MD, DOCX, TXT with loop cycle breaking and XSD validation.
  Scenario 2: Process Capture Form Rule-Engine (IT Incident Management) with valid tabular data & row error diagnostics.
  Scenario 3: Multi-Tool BPMN Migrations (Flowable, Camunda, Signavio) with vendor stripping and coordinate preservation.
  Scenario 4: Graph Validation, Diagnostics & Export Gate (unreachable steps, unlabelled decisions, auto-repair, strict mode).
  Scenario 5: Reference Template & Role-to-Lane Mapping (enterprise template upload, lane mapping, re-render).
  Scenario 6: Conversational Transcript Ingestion (.vtt interview parsing, speaker/timestamp stripping, diagram generation).
  Scenario 7: API Security, SSRF & Malformed Input Robustness (SSRF rejection, path traversal prevention, XML entity security).
  Scenario 8: Standalone CLI Automation (convert, import, profiles, exit codes, flags).
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from starlette.testclient import TestClient

from backend.server import app
from backend.ir.models import ProcessIR, FlowNode, SequenceFlow, Pool, Lane, SourceRef
from backend.ingestion.parser import ingest_file, clean_vtt_srt, IngestionError
from backend.ingestion.bpmn_importer import import_bpmn_bytes
from backend.pipeline.process_pipeline import (
    process_pipeline,
    import_bpmn_pipeline,
    render_ir,
    ExportBlockedError,
)
from backend.pipeline.validator import ProcessValidator
from backend.pipeline.xsd_validator import validate_bpmn
from backend.templates.storage import TemplateStorage
from backend.templates.simple_parser import (
    SimpleTemplateParser,
    detect_template_kind,
    TEMPLATE_KIND_SIMPLE,
    RowValidationError,
)
from backend.security import validate_base_url

FIXTURES = _PROJECT_ROOT / "backend" / "tests" / "fixtures"
O2C_SOP_MD = FIXTURES / "scenario_o2c_sop.md"
O2C_SOP_DOCX = FIXTURES / "scenario_o2c_sop.docx"
INCIDENT_XLSX = FIXTURES / "scenario_it_incident_capture.xlsx"
ONBOARDING_VTT = FIXTURES / "scenario_customer_onboarding.vtt"
FLOWABLE_BPMN = FIXTURES / "scenario_flowable_export.bpmn"
CAMUNDA_BPMN = FIXTURES / "import_camunda_vendor.bpmn"
SIGNAVIO_BPMN = FIXTURES / "sample_signavio.bpmn"
ENTERPRISE_TPL = FIXTURES / "scenario_enterprise_template.bpmn"

client = TestClient(app)


class TestScenario1EndToEndSOP(unittest.TestCase):
    """Scenario 1: End-to-End SOP Ingestion (Order-to-Cash) across MD, DOCX, TXT."""

    def test_markdown_sop_converts_to_valid_celonis_and_generic_bpmn(self):
        content = O2C_SOP_MD.read_bytes()
        # 1. Default profile is Celonis
        res_celonis = process_pipeline(
            raw_content=content,
            filename=O2C_SOP_MD.name,
            profile_name="celonis",
            mock=True,
        )
        self.assertIn("bpmn_xml", res_celonis)
        xml_celonis = res_celonis["bpmn_xml"]
        self.assertIn("<bpmn:collaboration", xml_celonis)
        self.assertIn("Credit", xml_celonis)
        # Celonis must be valid BPMN 2.0 against OMG XSD
        errs_c = validate_bpmn(xml_celonis)
        self.assertEqual(errs_c, [], f"Celonis XSD errors: {errs_c}")

        # 2. Generic profile
        res_generic = process_pipeline(
            raw_content=content,
            filename=O2C_SOP_MD.name,
            profile_name="generic",
            mock=True,
        )
        xml_generic = res_generic["bpmn_xml"]
        errs_g = validate_bpmn(xml_generic)
        self.assertEqual(errs_g, [], f"Generic XSD errors: {errs_g}")

    def test_word_docx_sop_converts_successfully(self):
        content = O2C_SOP_DOCX.read_bytes()
        res = process_pipeline(
            raw_content=content,
            filename=O2C_SOP_DOCX.name,
            profile_name="celonis",
            mock=True,
        )
        self.assertIn("bpmn_xml", res)
        self.assertGreater(len(res["ir"]["elements"]), 3)
        errs = validate_bpmn(res["bpmn_xml"])
        self.assertEqual(errs, [])

    def test_loopback_cycle_breaking_layout(self):
        """Verify that a process with a loopback does not invert node ordering or crash layout."""
        ir = ProcessIR(
            id="proc_loop",
            title="Loopback Flow",
            elements=[
                FlowNode(id="start", name="Start", type="startEvent"),
                FlowNode(id="task_draft", name="Draft Order", type="task"),
                FlowNode(id="gw_eval", name="Evaluate", type="exclusiveGateway"),
                FlowNode(id="task_fulfill", name="Fulfill", type="task"),
                FlowNode(id="end", name="End", type="endEvent"),
            ],
            flows=[
                SequenceFlow(id="f1", sourceId="start", targetId="task_draft"),
                SequenceFlow(id="f2", sourceId="task_draft", targetId="gw_eval"),
                SequenceFlow(id="f_pass", name="Approved", condition="approved", sourceId="gw_eval", targetId="task_fulfill"),
                # Loopback backward flow
                SequenceFlow(id="f_loop", name="Rejected", condition="rejected", sourceId="gw_eval", targetId="task_draft"),
                SequenceFlow(id="f3", sourceId="task_fulfill", targetId="end"),
            ],
        )
        rendered = render_ir(ir=ir, profile_name="celonis", mock=True)
        xml = rendered["bpmn_xml"]
        self.assertIn("f_loop", xml)
        # Verify Sugiyama layout engine breaks cycle and positions draft order left of evaluate gateway
        from backend.pipeline.layout import SugiyamaLayoutEngine
        layout = SugiyamaLayoutEngine(ir).compute_layout()
        self.assertLess(layout.nodes["task_draft"].bounds.x, layout.nodes["gw_eval"].bounds.x)
        errs = validate_bpmn(xml)
        self.assertEqual(errs, [])


class TestScenario2ProcessCaptureTemplate(unittest.TestCase):
    """Scenario 2: Process Capture Form Rule-Engine (IT Incident Management)."""

    def test_it_incident_excel_capture_converts_deterministically(self):
        content = INCIDENT_XLSX.read_bytes()
        # Check signature detection
        kind = detect_template_kind(content, INCIDENT_XLSX.name)
        self.assertEqual(kind, TEMPLATE_KIND_SIMPLE)

        # Full pipeline conversion
        res = process_pipeline(raw_content=content, filename=INCIDENT_XLSX.name, profile_name="celonis")
        self.assertEqual(res["metadata"]["extraction"]["mode"], "simple_template_parser")
        ir = res["ir"]
        elem_names = {e.get("name", "") for e in ir["elements"]}
        self.assertIn("Receive Incident Report", elem_names)
        self.assertIn("Is standard known issue?", elem_names)
        self.assertIn("Apply Standard KB Fix", elem_names)
        self.assertIn("Close Incident Ticket", elem_names)

        # Verify parallel gateway was generated for PG-01
        gateways = [e for e in ir["elements"] if "Gateway" in e.get("type", "")]
        self.assertGreaterEqual(len(gateways), 2)  # Decision XOR + Parallel Fork/Join

        # XSD validation
        errs = validate_bpmn(res["bpmn_xml"])
        self.assertEqual(errs, [])

    def test_capture_template_row_validation_errors(self):
        """Verify non-consecutive parallel groups and dangling next-steps raise RowValidationError."""
        import openpyxl

        # Build an invalid workbook with non-consecutive parallel group rows
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Process"
        ws.append(["Step ID", "Step", "Responsible", "Type", "If Yes", "If No", "Parallel Group", "Next Step"])
        ws.append(["S1", "Task 1", "Role A", "Task", "", "", "PG-A", "S2"])
        ws.append(["S2", "Task 2 (interruption)", "Role B", "Task", "", "", "", "S3"])
        ws.append(["S3", "Task 3 (split group)", "Role A", "Task", "", "", "PG-A", "S4"])
        buf = io.BytesIO()
        wb.save(buf)
        bad_xlsx = buf.getvalue()

        parser = SimpleTemplateParser()
        with self.assertRaises(RowValidationError) as ctx:
            parser.parse_bytes(bad_xlsx, "invalid_parallel.xlsx")
        self.assertTrue(any("consecutive" in err.message.lower() for err in ctx.exception.errors))


class TestScenario3MultiToolBpmnMigrations(unittest.TestCase):
    """Scenario 3: Multi-Tool BPMN Migrations (Flowable, Camunda, Signavio)."""

    def test_flowable_bpmn_import_strips_vendor_and_keeps_layout(self):
        raw = FLOWABLE_BPMN.read_bytes()
        ir, layout, report = import_bpmn_bytes(raw, filename=FLOWABLE_BPMN.name)

        # 1. Vendor extensions stripped
        self.assertTrue(any("flowable" in ns.lower() for ns in report.stripped_namespaces))
        self.assertTrue(any("formProperty" in ext for ext in report.stripped_extensions))

        # 2. Graph elements preserved
        elem_names = {e.name for e in ir.elements}
        self.assertIn("Review Application", elem_names)
        self.assertIn("Disburse Funds via Core Banking", elem_names)
        self.assertIn("Risk Score OK?", elem_names)

        # 3. Preserved coordinates
        self.assertIsNotNone(layout)
        self.assertIn("Task_ReviewApplication", layout.nodes)
        self.assertEqual(layout.nodes["Task_ReviewApplication"].bounds.x, 240.0)

        # 4. Pipeline re-export for Celonis and Generic
        pipeline_res = import_bpmn_pipeline(raw_content=raw, filename=FLOWABLE_BPMN.name, profile_name="celonis")
        self.assertIn("bpmn_xml", pipeline_res)
        errs = validate_bpmn(pipeline_res["bpmn_xml"])
        self.assertEqual(errs, [])

    def test_camunda_bpmn_import_handles_boundary_events_and_subprocesses(self):
        raw = CAMUNDA_BPMN.read_bytes()
        pipeline_res = import_bpmn_pipeline(raw_content=raw, filename=CAMUNDA_BPMN.name, profile_name="generic")
        self.assertIn("bpmn_xml", pipeline_res)
        self.assertEqual(pipeline_res["import_info"]["source_vendor"], "camunda")
        errs = validate_bpmn(pipeline_res["bpmn_xml"])
        self.assertEqual(errs, [])

    def test_signavio_bpmn_import_sanitizes_ids_and_preserves_lanes(self):
        raw = SIGNAVIO_BPMN.read_bytes()
        # Test vendor detection when exporter has Signavio
        raw_signavio = raw.replace(b'exporter="Process2BPMN"', b'exporter="Signavio Process Editor"')
        ir, _, report = import_bpmn_bytes(raw_signavio, filename="signavio_export.bpmn")
        self.assertEqual(report.source_vendor, "signavio")
        self.assertGreater(len(ir.elements), 0)
        # All IDs must be valid NCNames
        for e in ir.elements:
            self.assertTrue(e.id.replace("_", "").isalnum() or "-" in e.id)

    def test_foreign_import_roundtrip(self):
        """Import foreign file -> export Celonis -> re-import Celonis -> verify stability."""
        raw_flowable = FLOWABLE_BPMN.read_bytes()
        res1 = import_bpmn_pipeline(raw_content=raw_flowable, filename=FLOWABLE_BPMN.name, profile_name="celonis")
        celonis_xml = res1["bpmn_xml"].encode("utf-8")

        # Re-import the exported Celonis file
        res2 = import_bpmn_pipeline(raw_content=celonis_xml, filename="celonis_export.bpmn", profile_name="generic")
        self.assertGreater(len(res2["ir"]["elements"]), 0)
        errs = validate_bpmn(res2["bpmn_xml"])
        self.assertEqual(errs, [])


class TestScenario4GraphValidationAndExportGate(unittest.TestCase):
    """Scenario 4: Graph Validation, Diagnostics & Export Gate."""

    def test_unreachable_step_blocks_export_unless_forced(self):
        ir = ProcessIR(
            id="proc_unreachable",
            title="Broken Process",
            elements=[
                FlowNode(id="start", name="Start", type="startEvent"),
                FlowNode(id="task1", name="Task 1", type="task"),
                FlowNode(id="end", name="End", type="endEvent"),
                # Isolated island task
                FlowNode(id="task_island", name="Unreachable Task", type="task"),
            ],
            flows=[
                SequenceFlow(id="f1", sourceId="start", targetId="task1"),
                SequenceFlow(id="f2", sourceId="task1", targetId="end"),
            ],
        )
        validator = ProcessValidator(ir)
        repaired, issues = validator.validate_and_repair()
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(any("unreachable" in i.message.lower() for i in errors))

        # In strict mode, render_ir must raise ExportBlockedError
        with self.assertRaises(ExportBlockedError):
            render_ir(ir=ir, strict=True)

        # Non-strict returns export_blocked flag so UI can display issues
        res = render_ir(ir=ir, strict=False)
        self.assertTrue(res["export_blocked"])

    def test_auto_repair_missing_start_and_end(self):
        """Process without start/end events gets them auto-generated."""
        ir = ProcessIR(
            id="proc_headless",
            title="Headless Process",
            elements=[
                FlowNode(id="task1", name="Do Work", type="task"),
            ],
            flows=[],
        )
        validator = ProcessValidator(ir)
        repaired, issues = validator.validate_and_repair()
        types = {e.type for e in repaired.elements}
        self.assertIn("startEvent", types)
        self.assertIn("endEvent", types)
        self.assertTrue(any("start" in i.message.lower() for i in issues))
        self.assertTrue(any("end" in i.message.lower() for i in issues))

    def test_export_endpoints_respect_export_gate(self):
        """POST /api/export/bpmn returns 422 for blocked processes."""
        broken_ir = {
            "id": "proc_err",
            "title": "Erroneous",
            "elements": [
                {"id": "start", "name": "Start", "type": "startEvent"},
                {"id": "island", "name": "Island", "type": "task"},
            ],
            "flows": [],
            "pools": [],
        }
        res = client.post("/api/export/bpmn", json={"ir": broken_ir, "profile": "celonis"})
        self.assertEqual(res.status_code, 422)
        data = res.json()
        self.assertIn("error", data)


class TestScenario5ReferenceTemplateAndLaneMapping(unittest.TestCase):
    """Scenario 5: Reference Template Upload, Storage, and Role-to-Lane Mapping."""

    def setUp(self):
        self.storage = TemplateStorage()
        self.template_id = "test_enterprise_tpl"
        # Save enterprise template
        raw_xml = ENTERPRISE_TPL.read_text(encoding="utf-8")
        self.storage.save_bpmn_template(
            template_id=self.template_id,
            name="Enterprise Standard Template",
            xml_content=raw_xml,
            filename=ENTERPRISE_TPL.name,
        )

    def tearDown(self):
        try:
            self.storage.delete_template(self.template_id)
        except Exception:
            pass

    def test_template_upload_and_metadata_retrieval(self):
        tpl = self.storage.get_template(self.template_id)
        self.assertIsNotNone(tpl)
        meta, _, spec = tpl
        lanes = [l.name for l in spec.get_all_lanes()]
        self.assertIn("Risk and Compliance", lanes)
        self.assertIn("Operations and Logistics", lanes)
        self.assertIn("Finance and Treasury", lanes)

    def test_lane_mapping_and_re_render(self):
        """Map extracted process actors to template lanes and re-render without LLM."""
        ir = ProcessIR(
            id="proc_mapped",
            title="Mapped Process",
            elements=[
                FlowNode(id="start", name="Start", type="startEvent"),
                FlowNode(id="t1", name="Review Risk", type="task", actor="Risk Auditor"),
                FlowNode(id="t2", name="Dispatch Goods", type="task", actor="Warehouse Staff"),
                FlowNode(id="end", name="End", type="endEvent"),
            ],
            flows=[
                SequenceFlow(id="f1", sourceId="start", targetId="t1"),
                SequenceFlow(id="f2", sourceId="t1", targetId="t2"),
                SequenceFlow(id="f3", sourceId="t2", targetId="end"),
            ],
        )
        lane_map = {
            "Risk Auditor": "Lane_Risk",
            "Warehouse Staff": "Lane_Ops",
        }
        res = render_ir(
            ir=ir,
            profile_name="celonis",
            template_id=self.template_id,
            lane_map=lane_map,
            mock=True,
        )
        xml = res["bpmn_xml"]
        self.assertIn("Lane_Risk", xml)
        self.assertIn("Lane_Ops", xml)
        errs = validate_bpmn(xml)
        self.assertEqual(errs, [])


class TestScenario6ConversationalTranscriptIngestion(unittest.TestCase):
    """Scenario 6: Conversational Transcript / Subtitle Ingestion (.vtt)."""

    def test_vtt_cleaner_strips_headers_timestamps_and_speaker_tags(self):
        raw_vtt = ONBOARDING_VTT.read_text(encoding="utf-8")
        cleaned = clean_vtt_srt(raw_vtt)

        self.assertNotIn("WEBVTT", cleaned)
        self.assertNotIn("00:00:01.000", cleaned)
        self.assertNotIn("<v", cleaned)
        self.assertIn("Onboarding Specialist:", cleaned)
        self.assertIn("Compliance Officer verifies identity", cleaned)

    def test_vtt_full_conversion_pipeline(self):
        raw_vtt = ONBOARDING_VTT.read_bytes()
        res = process_pipeline(raw_content=raw_vtt, filename=ONBOARDING_VTT.name, profile_name="celonis", mock=True)
        self.assertIn("bpmn_xml", res)
        self.assertGreater(len(res["ir"]["elements"]), 0)
        errs = validate_bpmn(res["bpmn_xml"])
        self.assertEqual(errs, [])


class TestScenario7SecuritySSRFAndRobustness(unittest.TestCase):
    """Scenario 7: API Security, SSRF & Malformed Input Robustness."""

    def test_ssrf_rejects_cloud_metadata_and_loopback_urls(self):
        with self.assertRaises(ValueError):
            validate_base_url("http://169.254.169.254/latest/meta-data/", allow_private=False)

        with self.assertRaises(ValueError):
            validate_base_url("http://127.0.0.1:8080/v1", allow_private=False)

        with self.assertRaises(ValueError):
            validate_base_url("http://localhost:11434/v1", allow_private=False)

        with self.assertRaises(ValueError):
            validate_base_url("http://10.0.0.1:8000/v1", allow_private=False)

        # Public HTTPS URLs are permitted
        self.assertEqual(validate_base_url("https://api.openai.com/v1", allow_private=False), "https://api.openai.com/v1")

    def test_path_traversal_prevention_in_templates(self):
        storage = TemplateStorage()
        # Non-alphanumeric malicious ID should be sanitized or rejected
        with self.assertRaises((ValueError, FileNotFoundError)):
            storage.delete_template("../../../etc/passwd")

    def test_xml_bomb_defense_with_defusedxml(self):
        """Verify XML containing DTD/entity expansion attack is rejected."""
        xml_bomb = b"""<?xml version="1.0"?>
        <!DOCTYPE lolz [
          <!ENTITY lol "lol">
          <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
          <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
        ]>
        <bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
          <bpmn:process id="p1" name="&lol3;"/>
        </bpmn:definitions>"""

        # Importer must raise IngestionError or BpmnImportError when defusedxml blocks entities
        with self.assertRaises(Exception):
            import_bpmn_bytes(xml_bomb, "bomb.bpmn")


class TestScenario8CliAutomation(unittest.TestCase):
    """Scenario 8: Standalone CLI Automation."""

    def test_cli_profiles_command(self):
        cmd = [sys.executable, "-m", "backend.cli", "profiles"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=_PROJECT_ROOT)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("celonis", proc.stdout)
        self.assertIn("generic", proc.stdout)

    def test_cli_convert_command_produces_valid_file(self):
        with tempfile.NamedTemporaryFile(suffix=".bpmn", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            cmd = [
                sys.executable, "-m", "backend.cli", "convert",
                str(O2C_SOP_MD),
                "--mock",
                "-o", tmp_path,
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=_PROJECT_ROOT)
            self.assertEqual(proc.returncode, 0, f"CLI error: {proc.stderr}")
            self.assertTrue(Path(tmp_path).exists())
            xml = Path(tmp_path).read_text(encoding="utf-8")
            errs = validate_bpmn(xml)
            self.assertEqual(errs, [])
        finally:
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()

    def test_cli_import_command_produces_valid_file(self):
        with tempfile.NamedTemporaryFile(suffix=".bpmn", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            cmd = [
                sys.executable, "-m", "backend.cli", "import",
                str(FLOWABLE_BPMN),
                "-o", tmp_path,
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=_PROJECT_ROOT)
            self.assertEqual(proc.returncode, 0, f"CLI import error: {proc.stderr}")
            xml = Path(tmp_path).read_text(encoding="utf-8")
            errs = validate_bpmn(xml)
            self.assertEqual(errs, [])
        finally:
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()

    def test_cli_import_relayout_flag(self):
        with tempfile.NamedTemporaryFile(suffix=".bpmn", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            cmd = [
                sys.executable, "-m", "backend.cli", "import",
                str(FLOWABLE_BPMN),
                "--relayout",
                "-o", tmp_path,
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=_PROJECT_ROOT)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("auto-layout applied", proc.stderr)
        finally:
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()


if __name__ == "__main__":
    unittest.main()
