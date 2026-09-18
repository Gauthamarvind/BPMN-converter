import unittest
from pathlib import Path
from backend.server import process_pipeline, template_storage
from backend.templates.blank_generator import generate_blank_xlsx, generate_blank_docx
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
        # templateBindings should be None
        self.assertIsNone(res1["ir"].get("templateBindings"))
        # Byte-for-byte equality of the output XML when mock=True
        self.assertEqual(res1["bpmn_xml"], res2["bpmn_xml"])

    def test_pipeline_with_template(self):
        """Ensures template mode injects templateBindings and aligns with template."""
        res = process_pipeline(
            raw_content=self.sample_text.encode("utf-8"),
            filename="loan_process.txt",
            profile_name="camunda",
            mock=True,
            template_id="default_camunda"
        )
        self.assertTrue(res["success"])
        self.assertIsNotNone(res.get("template_info"))
        self.assertEqual(res["template_info"]["template_id"], "default_camunda")
        self.assertEqual(res["template_info"]["source_vendor"], "camunda")
        self.assertIn("bpmn_xml", res)
        self.assertIn("Lane_Initiator", res["bpmn_xml"])
        self.assertIsNotNone(res["ir"].get("templateBindings"))

    def test_blank_generators(self):
        """Tests blank XLSX and DOCX generators."""
        xlsx_bytes = generate_blank_xlsx(include_sample=True)
        self.assertGreater(len(xlsx_bytes), 1000)
        self.assertTrue(xlsx_bytes.startswith(b"PK"))

        docx_bytes = generate_blank_docx(include_sample=True)
        self.assertGreater(len(docx_bytes), 1000)
        self.assertTrue(docx_bytes.startswith(b"PK"))

    def test_lane_mapper(self):
        """Tests actor to lane mapping."""
        rec = template_storage.get_template("default_camunda")
        self.assertIsNotNone(rec)
        _, _, spec = rec
        mapper = LaneMapper(spec)
        mappings = mapper.map_actors(["Initiator", "Credit Approver", "Unknown Actor"], use_llm=False)
        self.assertEqual(len(mappings), 3)
        initiator_map = next((m for m in mappings if m.actor == "Initiator"), None)
        self.assertIsNotNone(initiator_map)
        self.assertEqual(initiator_map.lane_id, "Lane_Initiator")

    def test_doc_template_parser_csv(self):
        """Tests parsing tabular CSV process input."""
        csv_content = """Step,Task,Actor,Type,Next Steps
1,Submit Claim,Policyholder,User,2
2,Verify Coverage,Claims Adjuster,User,3;4
3,Approve Payout,Finance Manager,User,5
4,Reject Claim,Claims Adjuster,User,5
5,Close Case,System,Service,
"""
        parser = DocTemplateParser()
        ir = parser.parse_bytes(csv_content.encode("utf-8"), "claims.csv")
        self.assertGreater(len(ir.elements), 3)
        self.assertGreater(len(ir.flows), 2)
        actors = [l.name for p in ir.pools for l in p.lanes]
        self.assertIn("Policyholder", actors)


if __name__ == "__main__":
    unittest.main()
