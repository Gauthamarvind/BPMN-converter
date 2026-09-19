"""
Scope v2 phase 4: BPMN import from other tools.

Covers the importer itself (type mapping, vendor stripping, DI preservation, id sanitising),
the /api/import/bpmn endpoint, and a full round trip: import a foreign file, re-export it for
each target profile, and re-import the result.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from starlette.testclient import TestClient

from backend.server import app
from backend.ingestion.bpmn_importer import (
    BpmnImportError,
    import_bpmn_bytes,
    looks_like_bpmn,
    sanitize_id,
)
from backend.pipeline.process_pipeline import import_bpmn_pipeline
from backend.pipeline.xsd_validator import validate_bpmn

FIXTURES = _PROJECT_ROOT / "backend" / "tests" / "fixtures"
VENDOR_FILE = FIXTURES / "import_camunda_vendor.bpmn"
OWN_EXPORT = FIXTURES / "sample_signavio.bpmn"


class TestImporter(unittest.TestCase):
    def setUp(self):
        self.raw = VENDOR_FILE.read_bytes()

    def test_vendor_and_exporter_are_detected(self):
        _, _, report = import_bpmn_bytes(self.raw, filename=VENDOR_FILE.name)
        self.assertEqual(report.source_vendor, "camunda")
        self.assertIn("Camunda Modeler", report.exporter)

    def test_vendor_namespaces_and_extensions_are_stripped(self):
        _, _, report = import_bpmn_bytes(self.raw, filename=VENDOR_FILE.name)
        self.assertTrue(any("camunda" in ns for ns in report.stripped_namespaces))
        self.assertTrue(any("formData" in ext for ext in report.stripped_extensions))

    def test_graph_is_extracted_with_lanes_and_conditions(self):
        ir, _, _ = import_bpmn_bytes(self.raw, filename=VENDOR_FILE.name)
        names = {e.name for e in ir.elements}
        self.assertIn("Check invoice", names)
        self.assertIn("Release payment", names)

        lanes = {l.name for p in ir.pools for l in p.lanes}
        self.assertEqual(lanes, {"Accounts Payable", "Finance"})

        yes_flow = next(f for f in ir.flows if f.name == "Yes")
        self.assertIn("approved", yes_flow.condition)

    def test_unsupported_types_are_approximated_and_reported(self):
        ir, _, report = import_bpmn_bytes(self.raw, filename=VENDOR_FILE.name)
        rules = next(e for e in ir.elements if e.name == "Apply approval rules")
        self.assertEqual(rules.type, "serviceTask")
        self.assertTrue(any("business rule task" in w for w in report.warnings))

    def test_boundary_event_is_skipped_with_a_warning(self):
        ir, _, report = import_bpmn_bytes(self.raw, filename=VENDOR_FILE.name)
        self.assertNotIn("14 days", {e.name for e in ir.elements})
        self.assertTrue(any("boundaryEvent" in w for w in report.warnings))
        # …and the flow that hung off it is dropped rather than left dangling.
        self.assertTrue(all(f.sourceId != "BoundaryEvent_Timeout" for f in ir.flows))

    def test_original_coordinates_are_preserved(self):
        ir, layout, _ = import_bpmn_bytes(self.raw, filename=VENDOR_FILE.name)
        self.assertIsNotNone(layout)
        start = next(e for e in ir.elements if e.type == "startEvent")
        self.assertEqual(layout.nodes[start.id].bounds.x, 212.0)
        self.assertEqual(layout.nodes[start.id].bounds.y, 162.0)
        self.assertEqual(len(layout.pools), 1)
        self.assertEqual(len(layout.pools[0].lanes), 2)

    def test_rejects_non_bpmn_xml(self):
        with self.assertRaises(BpmnImportError):
            import_bpmn_bytes(b"<?xml version='1.0'?><root><a/></root>", filename="x.xml")

    def test_rejects_doctype(self):
        evil = b"<?xml version='1.0'?><!DOCTYPE d [<!ENTITY e 'x'>]><bpmn:definitions/>"
        with self.assertRaises(BpmnImportError):
            import_bpmn_bytes(evil, filename="evil.bpmn")

    def test_sanitize_id_is_stable_and_ncname_safe(self):
        used: dict = {}
        first = sanitize_id("{3F2B}-order step", "Node", used)
        again = sanitize_id("{3F2B}-order step", "Node", used)
        self.assertEqual(first, again)
        self.assertRegex(first, r"^[a-zA-Z_][a-zA-Z0-9_.-]*$")
        self.assertNotEqual(sanitize_id("99", "Node", used), sanitize_id("98", "Node", used))

    def test_looks_like_bpmn(self):
        self.assertTrue(looks_like_bpmn("x.bpmn", self.raw))
        self.assertFalse(looks_like_bpmn("x.docx", self.raw))
        self.assertFalse(looks_like_bpmn("x.xml", b"<html><body>no</body></html>"))


class TestImportPipeline(unittest.TestCase):
    def test_import_keeps_layout_and_produces_valid_bpmn(self):
        res = import_bpmn_pipeline(VENDOR_FILE.read_bytes(), filename=VENDOR_FILE.name)
        self.assertTrue(res["success"])
        self.assertEqual(res["import_info"]["original_layout"], True)
        self.assertEqual(res["metadata"]["extraction"]["mode"], "bpmn-import")
        self.assertEqual(res["lint_result"]["profile_name"], "celonis")
        self.assertEqual(validate_bpmn(res["bpmn_xml"]), [])
        # the preserved x/y of the start event survive into the exported DI
        self.assertIn('x="212.0"', res["bpmn_xml"])
        self.assertIn('y="162.0"', res["bpmn_xml"])

    def test_relayout_discards_source_coordinates(self):
        res = import_bpmn_pipeline(VENDOR_FILE.read_bytes(), filename=VENDOR_FILE.name, relayout=True)
        self.assertTrue(res["success"])
        self.assertFalse(res["import_info"]["original_layout"])
        self.assertEqual(validate_bpmn(res["bpmn_xml"]), [])

    def test_round_trip_through_both_profiles(self):
        for profile in ("celonis", "generic"):
            with self.subTest(profile=profile):
                first = import_bpmn_pipeline(
                    VENDOR_FILE.read_bytes(), filename=VENDOR_FILE.name, profile_name=profile
                )
                self.assertEqual(validate_bpmn(first["bpmn_xml"]), [])

                # Re-importing our own export must give back the same graph size.
                second = import_bpmn_pipeline(
                    first["bpmn_xml"].encode("utf-8"), filename="roundtrip.bpmn", profile_name=profile
                )
                self.assertEqual(
                    second["metadata"]["element_count"], first["metadata"]["element_count"]
                )
                self.assertEqual(second["metadata"]["flow_count"], first["metadata"]["flow_count"])

    def test_own_export_imports_cleanly(self):
        res = import_bpmn_pipeline(OWN_EXPORT.read_bytes(), filename=OWN_EXPORT.name)
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["metadata"]["element_count"], 5)
        self.assertEqual(validate_bpmn(res["bpmn_xml"]), [])


class TestImportEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_import_endpoint_returns_convert_shaped_payload(self):
        with open(VENDOR_FILE, "rb") as fh:
            res = self.client.post(
                "/api/import/bpmn",
                files={"file": (VENDOR_FILE.name, fh.read(), "application/xml")},
            )
        self.assertEqual(res.status_code, 200, res.text[:300])
        data = res.json()
        for key in ("success", "bpmn_xml", "ir", "validation_issues", "lint_result", "metadata"):
            self.assertIn(key, data)
        self.assertEqual(data["import_info"]["source_vendor"], "camunda")
        self.assertEqual(data["lint_result"]["profile_name"], "celonis")

    def test_import_endpoint_honours_profile_and_relayout(self):
        with open(VENDOR_FILE, "rb") as fh:
            res = self.client.post(
                "/api/import/bpmn",
                files={"file": (VENDOR_FILE.name, fh.read(), "application/xml")},
                data={"profile": "generic", "relayout": "true"},
            )
        self.assertEqual(res.status_code, 200, res.text[:300])
        data = res.json()
        self.assertEqual(data["lint_result"]["profile_name"], "generic")
        self.assertFalse(data["import_info"]["original_layout"])

    def test_import_endpoint_rejects_non_bpmn(self):
        res = self.client.post(
            "/api/import/bpmn",
            files={"file": ("notes.txt", b"1. do a thing", "text/plain")},
        )
        self.assertEqual(res.status_code, 415)

    def test_import_endpoint_reports_broken_bpmn(self):
        res = self.client.post(
            "/api/import/bpmn",
            files={"file": ("broken.bpmn", b"<?xml version='1.0'?><bpmn:definitions/>", "application/xml")},
        )
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["kind"], "BpmnImportError")


if __name__ == "__main__":
    unittest.main()
