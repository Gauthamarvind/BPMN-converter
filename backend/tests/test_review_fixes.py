"""
Regression tests for the QA review fixes (multi-user hardening, layout, export gate,
template management, parser rules, mock unification, chunk merging).

Each test names the finding it guards so a future change that re-breaks it is obvious.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from starlette.testclient import TestClient

from backend import security as sec
from backend.ir.models import ProcessIR, FlowNode, SequenceFlow, Pool, Lane
from backend.pipeline.graph_utils import compute_layered_ranks
from backend.pipeline.layout import SugiyamaLayoutEngine
from backend.pipeline.validator import ProcessValidator
from backend.pipeline.chunker import ProcessExtractor
from backend.pipeline.process_pipeline import process_pipeline, ExportBlockedError
from backend.llm.adapters.mock import MockAdapter
from backend.templates.simple_parser import SimpleTemplateParser, map_header_columns, RowValidationError
from backend.templates.bpmn_parser import parse_safe_xml
from backend.templates.storage import TemplateStorage
from backend.templates.blank_generator import build_xlsx_from_steps
from backend.server import app


MINIMAL_BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" id="D1" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:collaboration id="C1"><bpmn:participant id="P1" name="Org" processRef="Proc1"/></bpmn:collaboration>
  <bpmn:process id="Proc1"><bpmn:laneSet id="LS1"><bpmn:lane id="L1" name="Ops"/></bpmn:laneSet></bpmn:process>
  <bpmndi:BPMNDiagram id="Dg1"><bpmndi:BPMNPlane id="Pl1" bpmnElement="C1">
    <bpmndi:BPMNShape id="S1" bpmnElement="P1" isHorizontal="true"><dc:Bounds x="0" y="0" width="600" height="200"/></bpmndi:BPMNShape>
    <bpmndi:BPMNShape id="S2" bpmnElement="L1" isHorizontal="true"><dc:Bounds x="30" y="0" width="570" height="200"/></bpmndi:BPMNShape>
  </bpmndi:BPMNPlane></bpmndi:BPMNDiagram>
</bpmn:definitions>"""


def _loop_ir() -> ProcessIR:
    lane = Lane(id="Lane_1", name="Author")
    return ProcessIR(
        id="Loop",
        name="Loop",
        pools=[Pool(id="P", name="Pool", lanes=[lane])],
        elements=[
            FlowNode(id="Start", type="startEvent", name="Start", laneId="Lane_1"),
            FlowNode(id="Draft", type="task", name="Draft", laneId="Lane_1"),
            FlowNode(id="Review", type="exclusiveGateway", name="Approved?", laneId="Lane_1"),
            FlowNode(id="Publish", type="task", name="Publish", laneId="Lane_1"),
            FlowNode(id="End", type="endEvent", name="End", laneId="Lane_1"),
        ],
        flows=[
            SequenceFlow(id="f1", sourceId="Start", targetId="Draft"),
            SequenceFlow(id="f2", sourceId="Draft", targetId="Review"),
            SequenceFlow(id="f3", sourceId="Review", targetId="Publish", condition="Yes"),
            SequenceFlow(id="f4", sourceId="Review", targetId="Draft", condition="No"),
            SequenceFlow(id="f5", sourceId="Publish", targetId="End"),
        ],
    )


def _blocked_ir_dict() -> dict:
    """A process with an isolated node -> export_blocked."""
    return {
        "id": "Blocked", "name": "Blocked",
        "pools": [{"id": "P", "name": "Pool", "lanes": [{"id": "L", "name": "Lane"}]}],
        "elements": [
            {"id": "S", "type": "startEvent", "name": "Start", "laneId": "L"},
            {"id": "A", "type": "task", "name": "A", "laneId": "L"},
            {"id": "Orphan", "type": "task", "name": "Orphan", "laneId": "L"},
            {"id": "E", "type": "endEvent", "name": "End", "laneId": "L"},
        ],
        "flows": [
            {"id": "f1", "sourceId": "S", "targetId": "A"},
            {"id": "f2", "sourceId": "A", "targetId": "E"},
        ],
    }


# ---------------------------------------------------------------------------
# G-LLM: the document text must reach the model
# ---------------------------------------------------------------------------

class TestPromptSubstitution(unittest.TestCase):
    def test_extraction_prompt_contains_document_text(self):
        extractor = ProcessExtractor(provider=MockAdapter())
        prompt = extractor.render_prompt("The clerk files the invoice.", "Invoice Handling")
        self.assertIn("The clerk files the invoice.", prompt)
        self.assertNotIn("{{CHUNK_TEXT}}", prompt)
        self.assertNotIn("{{POOLS_HINT}}", prompt)
        self.assertIn("Invoice Handling", prompt)


# ---------------------------------------------------------------------------
# G6: loops in the layout
# ---------------------------------------------------------------------------

class TestLayoutLoops(unittest.TestCase):
    def test_graph_utils_break_cycle_at_loop_back(self):
        ranks, back = compute_layered_ranks(
            ["s", "1", "2", "3", "e"],
            [("s", "1"), ("1", "2"), ("2", "3"), ("3", "1"), ("3", "e")],
            ["s"],
        )
        self.assertEqual(back, {("3", "1")})
        self.assertLess(ranks["1"], ranks["2"])
        self.assertLess(ranks["2"], ranks["3"])
        self.assertLess(ranks["3"], ranks["e"])

    def test_loop_target_stays_left_of_gateway(self):
        ir = _loop_ir()
        repaired, _ = ProcessValidator(ir).validate_and_repair()
        engine = SugiyamaLayoutEngine(repaired)
        layout = engine.compute_layout()
        self.assertLess(layout.nodes["Draft"].bounds.x, layout.nodes["Review"].bounds.x)
        self.assertLess(layout.nodes["Review"].bounds.x, layout.nodes["Publish"].bounds.x)
        self.assertIn(("Review", "Draft"), engine.back_edges)
        # the loop edge is routed underneath both nodes
        wps = layout.edges["f4"].waypoints
        self.assertGreater(wps[1].y, layout.nodes["Review"].bounds.y + layout.nodes["Review"].bounds.height)
        # and stays inside the lane
        lane_bottom = layout.pools[0].lanes[0].bounds.y + layout.pools[0].lanes[0].bounds.height
        self.assertLessEqual(wps[1].y, lane_bottom)


# ---------------------------------------------------------------------------
# G9: one mock engine
# ---------------------------------------------------------------------------

class TestMockUnification(unittest.TestCase):
    TEXT = "1. Customer submits order.\n2. Sales reviews order.\n3. Warehouse ships order."

    def test_mock_adapter_emits_ir_keys_the_loader_understands(self):
        parsed, raw, usage = MockAdapter().complete(
            [{"role": "user", "content": "## Process Document Fragment\n```\n" + self.TEXT + "\n```\n## Required JSON Schema\nreturn json"}]
        )
        self.assertIsNotNone(parsed)
        self.assertTrue(all("sourceId" in f and "targetId" in f for f in parsed["flows"]))
        ir = ProcessIR.from_dict(parsed)
        self.assertGreaterEqual(len(ir.flows), 3)

    def test_provider_mock_and_mock_flag_produce_identical_ir(self):
        a = process_pipeline(self.TEXT.encode(), "steps.txt", mock=True)
        b = process_pipeline(self.TEXT.encode(), "steps.txt", mock=False, provider_name="mock")
        self.assertEqual(a["ir"], b["ir"])
        self.assertEqual(b["metadata"]["extraction"]["mode"], "deterministic_rule_engine")
        self.assertFalse(b["export_blocked"])


# ---------------------------------------------------------------------------
# G8: chunk merge fallback keeps every element and stays connected
# ---------------------------------------------------------------------------

class TestDeterministicUnion(unittest.TestCase):
    def _frag(self, n: int) -> ProcessIR:
        lane = Lane(id="Lane_1", name="Ops")  # same ids in every fragment on purpose
        return ProcessIR(
            id="Process_1",
            pools=[Pool(id="Participant_1", name="Org", lanes=[lane])],
            elements=[
                FlowNode(id="Event_start", type="startEvent", name="Start", laneId="Lane_1"),
                FlowNode(id="Activity_1", type="task", name=f"Task {n}", laneId="Lane_1"),
                FlowNode(id="Event_end", type="endEvent", name="End", laneId="Lane_1"),
            ],
            flows=[
                SequenceFlow(id="Flow_1", sourceId="Event_start", targetId="Activity_1"),
                SequenceFlow(id="Flow_2", sourceId="Activity_1", targetId="Event_end"),
            ],
        )

    def test_union_namespaces_and_stitches(self):
        extractor = ProcessExtractor(provider=MockAdapter())
        merged = extractor._deterministic_union([self._frag(1), self._frag(2), self._frag(3)], "Merged")
        names = {e.name for e in merged.elements}
        self.assertEqual({"Task 1", "Task 2", "Task 3", "Start", "End"}, names)
        self.assertEqual(1, sum(1 for e in merged.elements if e.type == "startEvent"))
        self.assertEqual(1, sum(1 for e in merged.elements if e.type == "endEvent"))
        self.assertEqual(1, len(merged.pools[0].lanes))
        repaired, issues = ProcessValidator(merged).validate_and_repair()
        self.assertFalse(any(i.severity == "ERROR" for i in issues), [i.message for i in issues])


# ---------------------------------------------------------------------------
# G10: table parser rules
# ---------------------------------------------------------------------------

class TestParserRules(unittest.TestCase):
    def test_notes_column_is_not_if_no(self):
        cols = map_header_columns(["Step ID", "Step", "Responsible", "Type", "If Yes → Step", "If No → Step", "Next Step", "Notes"])
        self.assertEqual(cols["if_no"], 5)
        self.assertEqual(cols["description"], 7)
        self.assertEqual(cols["next_step"], 6)

    def _steps_ir(self, steps):
        xlsx = build_xlsx_from_steps(process_name="T", steps=steps)
        return SimpleTemplateParser().parse_bytes(xlsx, "t.xlsx")

    def test_decision_with_next_step_is_reported(self):
        parser = SimpleTemplateParser()
        from backend.templates.simple_parser import StepRow
        rows = [
            StepRow(step_id="1", step="Check", responsible="A", type="Decision", if_yes="2", if_no="2", next_step="2", row_number=2),
            StepRow(step_id="2", step="Done", responsible="A", type="End", row_number=3),
        ]
        ok, errors, warnings = parser.validate_rows(rows)
        self.assertTrue(ok, [e.message for e in errors])
        self.assertTrue(any("Next Step" in w.column and "ignored" in w.message for w in warnings))

    def test_non_contiguous_parallel_group_is_rejected(self):
        steps = [
            {"step_id": "1", "step": "Kickoff", "responsible": "PM", "type": "Task"},
            {"step_id": "2", "step": "Build A", "responsible": "Dev", "type": "Task", "parallel_group": "G1"},
            {"step_id": "3", "step": "Write docs", "responsible": "Writer", "type": "Task"},
            {"step_id": "4", "step": "Build B", "responsible": "Dev", "type": "Task", "parallel_group": "G1"},
            {"step_id": "5", "step": "Ship", "responsible": "PM", "type": "Task", "next_step": "END"},
        ]
        with self.assertRaises(RowValidationError) as ctx:
            self._steps_ir(steps)
        self.assertTrue(any("consecutive rows" in i.message for i in ctx.exception.issues))


# ---------------------------------------------------------------------------
# G7: XML hardening
# ---------------------------------------------------------------------------

class TestXmlHardening(unittest.TestCase):
    def test_internal_entity_expansion_rejected(self):
        bomb = '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;">]><a>&lol2;</a>'
        with self.assertRaises(ValueError):
            parse_safe_xml(bomb)

    def test_plain_bpmn_still_parses(self):
        self.assertTrue(parse_safe_xml(MINIMAL_BPMN).tag.endswith("definitions"))


# ---------------------------------------------------------------------------
# Template storage: traversal, ownership, save_template
# ---------------------------------------------------------------------------

class TestTemplateStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = TemplateStorage(root_dir=Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_traversal_ids_are_rejected(self):
        for bad in ("..", "../..", "a/b", "../default_camunda"):
            with self.assertRaises(ValueError):
                self.storage.delete_template(bad)
            self.assertIsNone(self.storage.get_template(bad))
        self.assertTrue(Path(self.tmp.name).exists())

    def test_save_template_and_ownership(self):
        meta, _ = self.storage.save_template(MINIMAL_BPMN, "corp.bpmn", name="Corp", owner_id="alice")
        self.assertTrue(meta.id.startswith("tpl_corp"))
        self.assertIn(meta.id, [t.id for t in self.storage.list_templates("alice")])
        self.assertNotIn(meta.id, [t.id for t in self.storage.list_templates("bob")])
        self.assertIsNone(self.storage.get_template(meta.id, user_id="bob"))
        with self.assertRaises(PermissionError):
            self.storage.delete_template(meta.id, user_id="bob")
        with self.assertRaises(PermissionError):
            self.storage.delete_template("default_camunda", user_id="alice")
        self.assertTrue(self.storage.delete_template(meta.id, user_id="alice"))

    def test_per_user_default(self):
        self.storage.set_default("default_signavio", user_id="alice")
        alice = {t.id: t.is_default for t in self.storage.list_templates("alice")}
        bob = {t.id: t.is_default for t in self.storage.list_templates("bob")}
        self.assertTrue(alice["default_signavio"])
        self.assertFalse(bob["default_signavio"])
        self.assertTrue(bob["default_camunda"])


# ---------------------------------------------------------------------------
# API level: routes, gate, bulk export, SSRF, auth
# ---------------------------------------------------------------------------

class TestApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_ui_template_routes_exist(self):
        res = self.client.post(
            "/api/templates",
            files={"file": ("corp.bpmn", MINIMAL_BPMN.encode(), "application/xml")},
            data={"name": "Corp Template", "description": "d"},
        )
        self.assertEqual(res.status_code, 200, res.text[:300])
        tid = res.json()["template"]["id"]
        self.assertEqual(res.json()["template"]["name"], "Corp Template")
        try:
            dl = self.client.get(f"/api/templates/{tid}/download")
            self.assertEqual(dl.status_code, 200)
            self.assertIn("bpmn:definitions", dl.text)
        finally:
            self.assertEqual(self.client.delete(f"/api/templates/{tid}").status_code, 200)

    def test_health_hides_key_hint_when_hosted(self):
        old = (sec.security.auth_mode, sec.security.expose_server_config)
        try:
            sec.security.auth_mode, sec.security.expose_server_config = "proxy", False
            data = self.client.get("/api/health").json()
            self.assertEqual(data["api_key_hint"], "")
            self.assertEqual(data["base_url"], "")
            self.assertEqual(data["auth_mode"], "proxy")
        finally:
            sec.security.auth_mode, sec.security.expose_server_config = old

    def test_auth_required_in_proxy_and_token_modes(self):
        old = (sec.security.auth_mode, sec.security.api_token)
        try:
            sec.security.auth_mode = "proxy"
            self.assertEqual(self.client.get("/api/profiles").status_code, 401)
            self.assertEqual(self.client.get("/api/profiles", headers={"X-Forwarded-User": "alice"}).status_code, 200)
            self.assertEqual(self.client.get("/api/health").status_code, 200)  # public

            sec.security.auth_mode, sec.security.api_token = "token", "s3cret"
            self.assertEqual(self.client.get("/api/profiles").status_code, 401)
            self.assertEqual(self.client.get("/api/profiles", headers={"Authorization": "Bearer wrong"}).status_code, 401)
            self.assertEqual(self.client.get("/api/profiles", headers={"Authorization": "Bearer s3cret"}).status_code, 200)
        finally:
            sec.security.auth_mode, sec.security.api_token = old

    def test_base_url_ssrf_rejected_when_private_disallowed(self):
        old = sec.security.allow_private_base_urls
        try:
            sec.security.allow_private_base_urls = False
            res = self.client.post("/api/convert-json", json={
                "text": "1. a\n2. b", "provider": "openai_compatible", "base_url": "http://169.254.169.254/latest",
            })
            self.assertEqual(res.status_code, 400)
            self.assertIn("base_url", res.json()["detail"])
        finally:
            sec.security.allow_private_base_urls = old

    def test_strict_conversion_refuses_blocked_process(self):
        res = self.client.post("/api/render", json={"ir": _blocked_ir_dict(), "profile": "generic", "strict": True})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["kind"], "ExportBlockedError")
        # non-strict still returns the XML for preview, flagged
        res2 = self.client.post("/api/render", json={"ir": _blocked_ir_dict(), "profile": "generic"})
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["export_blocked"])

    def test_bulk_export_refuses_blocked_process(self):
        res = self.client.post("/api/export/bulk", json={"process_name": "x", "ir": _blocked_ir_dict()})
        self.assertEqual(res.status_code, 422)

    def test_bulk_export_contains_distinct_profiles(self):
        ir = _loop_ir().to_dict()
        res = self.client.post("/api/export/bulk", json={"process_name": "Loop Demo", "ir": ir, "svg": "<svg/>"})
        self.assertEqual(res.status_code, 200, res.text[:300])
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        names = set(zf.namelist())
        for p in ("generic", "camunda", "signavio", "celonis", "aris"):
            self.assertIn(f"loop_demo_{p}.bpmn", names)
        self.assertIn("loop_demo.svg", names)
        self.assertIn("manifest.json", names)
        xmls = {p: zf.read(f"loop_demo_{p}.bpmn").decode() for p in ("generic", "camunda", "signavio", "celonis", "aris")}
        self.assertGreater(len(set(xmls.values())), 1, "vendor profiles must not produce identical files")

    def test_export_bpmn_single_profile(self):
        res = self.client.post("/api/export/bpmn", json={"process_name": "Loop", "ir": _loop_ir().to_dict(), "profile": "camunda"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("bpmn:definitions", res.text)

    def test_spa_never_serves_outside_dist(self):
        dist = _PROJECT_ROOT / "dist"
        if not (dist / "index.html").is_file():
            self.skipTest("frontend not built")
        res = self.client.get("/../backend/config.py")
        self.assertNotIn("LLMConfig", res.text)

    def test_threadpool_convert_still_works(self):
        res = self.client.post("/api/convert", files={"file": ("s.txt", b"1. one\n2. two", "text/plain")}, data={"mock": "true"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])


if __name__ == "__main__":
    unittest.main()
