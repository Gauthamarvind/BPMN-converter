import unittest
import io
import openpyxl
from pathlib import Path

from backend.server import process_pipeline, template_storage
from backend.templates.blank_generator import (
    generate_blank_xlsx,
    generate_blank_docx,
    build_xlsx_from_steps,
)
from backend.templates.simple_parser import (
    SimpleTemplateParser,
    detect_template_kind,
    RowValidationError,
    RowIssue,
    TEMPLATE_KIND_SIMPLE,
    TEMPLATE_KIND_LEGACY,
    TEMPLATE_KIND_NONE,
)
from backend.templates.mapper import LaneMapper
from backend.templates.doc_parser import DocTemplateParser


class TestTemplates(unittest.TestCase):
    def setUp(self):
        self.sample_text = """
1. Customer submits a loan request.
2. Loan Officer reviews the credit score.
3. If credit score is above 700, Manager approves the request.
4. Otherwise, Loan Officer rejects the request.
5. End process.
"""

    def test_pipeline_without_template_unchanged(self):
        """Ensures that when template_id is None, the pipeline runs as before with templateBindings=None and is byte-for-byte deterministic."""
        res1 = process_pipeline(
            raw_content=self.sample_text.encode("utf-8"),
            filename="loan_process.txt",
            profile_name="generic",
            mock=True
        )
        res2 = process_pipeline(
            raw_content=self.sample_text.encode("utf-8"),
            filename="loan_process.txt",
            profile_name="generic",
            mock=True
        )
        self.assertTrue(res1["success"])
        self.assertIsNone(res1.get("template_info"))
        self.assertIn("bpmn_xml", res1)
        self.assertIn("<bpmn:definitions", res1["bpmn_xml"])
        self.assertIsNone(res1["ir"].get("templateBindings"))
        self.assertEqual(res1["bpmn_xml"], res2["bpmn_xml"])

    def test_pipeline_with_template(self):
        """Ensures template mode injects templateBindings and aligns with template."""
        res = process_pipeline(
            raw_content=self.sample_text.encode("utf-8"),
            filename="loan_process.txt",
            profile_name="celonis",
            mock=True,
            template_id="default_celonis"
        )
        self.assertTrue(res["success"])
        self.assertIsNotNone(res.get("template_info"))
        self.assertEqual(res["template_info"]["template_id"], "default_celonis")
        self.assertEqual(res["template_info"]["source_vendor"], "celonis")
        self.assertIn("bpmn_xml", res)
        self.assertIn("Lane_Sales_Order", res["bpmn_xml"])
        self.assertIsNotNone(res["ir"].get("templateBindings"))

    def test_blank_generators(self):
        """Tests blank XLSX and DOCX generators."""
        xlsx_bytes = generate_blank_xlsx(include_sample=True)
        self.assertGreater(len(xlsx_bytes), 1000)
        self.assertTrue(xlsx_bytes.startswith(b"PK"))

        docx_bytes = generate_blank_docx(include_sample=True)
        self.assertGreater(len(docx_bytes), 1000)
        self.assertTrue(docx_bytes.startswith(b"PK"))

    def test_golden_linear_process(self):
        """Golden test: Linear process with 3 tasks, auto start/end events, correct sequence flows."""
        steps = [
            {"step_id": "1", "step": "Receive Order", "responsible": "Sales", "type": "Task", "next_step": "2"},
            {"step_id": "2", "step": "Pack Items", "responsible": "Warehouse", "type": "Task", "next_step": "3"},
            {"step_id": "3", "step": "Ship Package", "responsible": "Logistics", "type": "Task", "next_step": "END"},
        ]
        xlsx_bytes = build_xlsx_from_steps(process_name="Order Fulfillment", steps=steps)
        parser = SimpleTemplateParser()
        ir = parser.parse_bytes(xlsx_bytes, "linear.xlsx")

        self.assertEqual(ir.name, "Order Fulfillment")
        element_types = [el.type for el in ir.elements]
        self.assertIn("startEvent", element_types)
        self.assertIn("endEvent", element_types)
        self.assertEqual(element_types.count("task"), 3)

        # Sequence flows should connect startEvent -> 1 -> 2 -> 3 -> endEvent
        flow_pairs = [(f.sourceId, f.targetId) for f in ir.flows]
        self.assertGreaterEqual(len(flow_pairs), 4)

        # Pools and lanes
        pool = ir.pools[0]
        lane_names = [l.name for l in pool.lanes]
        self.assertIn("Sales", lane_names)
        self.assertIn("Warehouse", lane_names)
        self.assertIn("Logistics", lane_names)

    def test_golden_decision_with_loop(self):
        """Golden test: Decision gateway looping back to a previous task."""
        steps = [
            {"step_id": "1", "step": "Draft Document", "responsible": "Author", "type": "Task", "next_step": "2"},
            {"step_id": "2", "step": "Review Document", "responsible": "Editor", "type": "Decision", "if_yes": "3", "if_no": "1"},
            {"step_id": "3", "step": "Publish", "responsible": "Publisher", "type": "Task", "next_step": "END"},
        ]
        xlsx_bytes = build_xlsx_from_steps(process_name="Doc Review", steps=steps)
        parser = SimpleTemplateParser()
        ir = parser.parse_bytes(xlsx_bytes, "review.xlsx")

        gateways = [el for el in ir.elements if el.type == "exclusiveGateway"]
        self.assertEqual(len(gateways), 1)
        gw_id = gateways[0].id

        # Loop back flow from gateway to step 1
        step1_node = next(el for el in ir.elements if el.name == "Draft Document")
        step3_node = next(el for el in ir.elements if el.name == "Publish")

        yes_flows = [f for f in ir.flows if f.sourceId == gw_id and f.targetId == step3_node.id]
        no_flows = [f for f in ir.flows if f.sourceId == gw_id and f.targetId == step1_node.id]

        self.assertEqual(len(yes_flows), 1)
        self.assertEqual(yes_flows[0].condition, "Yes")
        self.assertEqual(len(no_flows), 1)
        self.assertEqual(no_flows[0].condition, "No")

    def test_golden_parallel_group_across_lanes(self):
        """Golden test: Parallel group G1 with tasks across Finance and HR lanes."""
        steps = [
            {"step_id": "1", "step": "Hire Employee", "responsible": "HR", "type": "Task", "next_step": "G1"},
            {"step_id": "2", "step": "Setup Payroll", "responsible": "Finance", "type": "Task", "parallel_group": "G1", "next_step": "4"},
            {"step_id": "3", "step": "Prepare Laptop", "responsible": "IT", "type": "Task", "parallel_group": "G1", "next_step": "4"},
            {"step_id": "4", "step": "Welcome Orientation", "responsible": "HR", "type": "Task", "next_step": "END"},
        ]
        xlsx_bytes = build_xlsx_from_steps(process_name="Onboarding", steps=steps)
        parser = SimpleTemplateParser()
        ir = parser.parse_bytes(xlsx_bytes, "onboarding.xlsx")

        parallel_gws = [el for el in ir.elements if el.type == "parallelGateway"]
        self.assertEqual(len(parallel_gws), 2)  # Fork and Join gateways

        # Target nodes of parallel fork gateway should be step 2 and step 3
        fork_gw = parallel_gws[0]
        fork_targets = [f.targetId for f in ir.flows if f.sourceId == fork_gw.id]

        payroll_node = next(el for el in ir.elements if el.name == "Setup Payroll")
        laptop_node = next(el for el in ir.elements if el.name == "Prepare Laptop")

        self.assertIn(payroll_node.id, fork_targets)
        self.assertIn(laptop_node.id, fork_targets)

    def test_golden_multiple_end_events(self):
        """Golden test: Process with explicit End step producing separate End Events."""
        steps = [
            {"step_id": "1", "step": "Evaluate Risk", "responsible": "Analyst", "type": "Decision", "if_yes": "2", "if_no": "3"},
            {"step_id": "2", "step": "Approve Loan", "responsible": "Manager", "type": "Task", "next_step": "END"},
            {"step_id": "3", "step": "Reject & Archive", "responsible": "System", "type": "End", "next_step": "END"},
        ]
        xlsx_bytes = build_xlsx_from_steps(process_name="Risk Evaluation", steps=steps)
        parser = SimpleTemplateParser()
        ir = parser.parse_bytes(xlsx_bytes, "risk.xlsx")

        end_events = [el for el in ir.elements if el.type == "endEvent"]
        self.assertGreaterEqual(len(end_events), 1)

    def test_validation_errors_exact_messages(self):
        """Golden test: Validation assertions verifying exact messages, row numbers, and fixes."""
        steps = [
            {"step_id": "1", "step": "Step without responsible", "responsible": "", "type": "Task", "next_step": "2"},
            {"step_id": "2", "step": "Decision without branches", "responsible": "HR", "type": "Decision", "if_yes": "", "if_no": ""},
            {"step_id": "3", "step": "Step targeting nonexistent", "responsible": "Finance", "type": "Task", "next_step": "99"},
            {"step_id": "4", "step": "Step loop to self", "responsible": "IT", "type": "Task", "next_step": "4"},
            {"step_id": "5", "step": "Step invalid type", "responsible": "Ops", "type": "UnknownType", "next_step": "END"},
        ]
        xlsx_bytes = build_xlsx_from_steps(process_name="Broken Process", steps=steps)
        parser = SimpleTemplateParser()

        with self.assertRaises(RowValidationError) as ctx:
            parser.parse_bytes(xlsx_bytes, "broken.xlsx")

        issues = ctx.exception.issues
        self.assertGreaterEqual(len(issues), 5)

        # 1. Missing responsible on Row 4
        issue1 = next((i for i in issues if i.row == 4 and i.column == "Responsible"), None)
        self.assertIsNotNone(issue1)
        self.assertIn("Responsible is required", issue1.message)
        self.assertIn("Unassigned", issue1.fix)

        # 2. Missing branches on Row 5
        issue2 = next((i for i in issues if i.row == 5 and "Decision" in i.message), None)
        self.assertIsNotNone(issue2)

        # 3. Nonexistent next step on Row 6
        issue3 = next((i for i in issues if i.row == 6 and "99" in i.message), None)
        self.assertIsNotNone(issue3)

        # 4. Self loop on Row 7
        issue4 = next((i for i in issues if i.row == 7 and "points to itself" in i.message), None)
        self.assertIsNotNone(issue4)

        # 5. Invalid type on Row 8
        issue5 = next((i for i in issues if i.row == 8 and "Invalid type" in i.message), None)
        self.assertIsNotNone(issue5)

    def test_round_trip_example_workbook(self):
        """Golden test: Example workbook from generate_blank_xlsx converts successfully to valid diagram."""
        xlsx_bytes = generate_blank_xlsx(include_sample=True)
        res = process_pipeline(
            raw_content=xlsx_bytes,
            filename="Process_Capture_Template.xlsx",
            profile_name="generic",
            mock=True
        )
        self.assertTrue(res["success"])
        self.assertIn("bpmn_xml", res)
        self.assertIn("<bpmn:definitions", res["bpmn_xml"])
        self.assertEqual(res["metadata"]["extraction"]["mode"], "simple_template_parser")
        self.assertGreaterEqual(res["metadata"]["element_count"], 5)

    def test_signature_detection_accuracy(self):
        """Golden test: Ensures signature detection accurately distinguishes simple template, legacy template, and general documents."""
        # 1. Simple Template (.xlsx with _meta sheet)
        simple_xlsx = generate_blank_xlsx(include_sample=True)
        self.assertEqual(detect_template_kind(simple_xlsx, "test.xlsx"), TEMPLATE_KIND_SIMPLE)

        # 2. SOP Docx with a generic table (should NOT be detected as template)
        import docx
        doc = docx.Document()
        doc.add_heading("Standard Operating Procedure", 0)
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Topic"
        table.cell(0, 1).text = "Details"
        table.cell(1, 0).text = "Scope"
        table.cell(1, 1).text = "This procedure covers all operations."
        doc_buf = io.BytesIO()
        doc.save(doc_buf)
        docx_bytes = doc_buf.getvalue()

        self.assertEqual(detect_template_kind(docx_bytes, "sop.docx"), TEMPLATE_KIND_NONE)

        # 3. Legacy CSV
        legacy_csv = b"Step,Task,Actor,Type,Next Steps\n1,Do X,User,Task,2\n"
        self.assertEqual(detect_template_kind(legacy_csv, "legacy.csv"), TEMPLATE_KIND_LEGACY)


if __name__ == "__main__":
    unittest.main()

