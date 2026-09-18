"""
Golden-file tests for the fill-in template pipeline.

Each workbook in backend/tests/golden/template_workbooks/ is converted through the same
pipeline the API and CLI use, and the XML must match the committed golden .bpmn byte for byte.
Regenerate the goldens deliberately with:  python -m backend.tests.test_golden_templates --update
"""

from __future__ import annotations
import sys
import unittest
from pathlib import Path

from backend.pipeline.process_pipeline import process_pipeline
from backend.pipeline.xsd_validator import validate_bpmn

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
WORKBOOK_DIR = GOLDEN_DIR / "template_workbooks"
CASES = ["linear", "decision_with_loop", "parallel_across_lanes", "multiple_end_events"]


def _convert(case: str) -> dict:
    raw = (WORKBOOK_DIR / f"{case}.xlsx").read_bytes()
    return process_pipeline(raw, f"{case}.xlsx", mock=True)


class TestGoldenTemplates(unittest.TestCase):
    def test_golden_outputs_match(self):
        for case in CASES:
            with self.subTest(case=case):
                result = _convert(case)
                expected = (GOLDEN_DIR / f"{case}.bpmn").read_text(encoding="utf-8")
                self.assertEqual(result["bpmn_xml"], expected, f"{case}: output drifted from golden file")
                self.assertFalse(result["export_blocked"], f"{case}: golden case must not be export-blocked")
                self.assertEqual(validate_bpmn(result["bpmn_xml"]), [], f"{case}: XSD errors")

    def test_golden_structure(self):
        ir = _convert("decision_with_loop")["ir"]
        gateways = [e for e in ir["elements"] if e["type"] == "exclusiveGateway"]
        self.assertEqual(len(gateways), 1)
        labels = sorted(f["name"] for f in ir["flows"] if f["sourceId"] == gateways[0]["id"])
        self.assertEqual(labels, ["No", "Yes"])
        loops = [q for q in ir["openQuestions"] if "Loop detected" in q["question"]]
        self.assertEqual(len(loops), 1, "exactly one real loop must be reported")

        ir = _convert("parallel_across_lanes")["ir"]
        self.assertEqual(sum(1 for e in ir["elements"] if e["type"] == "parallelGateway"), 2)
        self.assertEqual([q for q in ir["openQuestions"] if "Loop detected" in q["question"]], [],
                         "a parallel group must not be reported as a loop")
        lanes = {lane["name"] for pool in ir["pools"] for lane in pool["lanes"]}
        self.assertTrue({"Engineering", "Marketing"} <= lanes)

        ir = _convert("multiple_end_events")["ir"]
        self.assertGreaterEqual(sum(1 for e in ir["elements"] if e["type"] == "endEvent"), 2)

    def test_source_refs_point_at_sheet_rows(self):
        ir = _convert("linear")["ir"]
        tasks = [e for e in ir["elements"] if e["type"] == "task"]
        self.assertTrue(tasks)
        for task in tasks:
            self.assertTrue(task["sourceRefs"], f"{task['id']} has no sourceRefs")
            self.assertIn("Process:row ", task["sourceRefs"][0]["sourceLocation"])
            self.assertTrue(task["sourceRefs"][0]["textSnippet"])


if __name__ == "__main__":
    if "--update" in sys.argv:
        for case in CASES:
            (GOLDEN_DIR / f"{case}.bpmn").write_text(_convert(case)["bpmn_xml"], encoding="utf-8")
            print(f"updated {case}.bpmn")
    else:
        unittest.main()
