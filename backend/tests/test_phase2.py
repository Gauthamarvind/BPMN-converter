"""
Unit test suite for Phase 2:
- Document Ingestion (TXT, MD, VTT, SRT, CSV, DOCX)
- Column role detection in spreadsheets
- LLM Provider Interface & Factory
- Structured output self-healing & fence stripping
- Token chunking and Map-Reduce logic
"""

import sys
import unittest
import io
from pathlib import Path

# Add project root to sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.ingestion.parser import (
    clean_vtt_srt,
    parse_csv_content,
    detect_column_roles,
    ingest_file,
    parse_docx_bytes
)
from backend.llm.base import LLMProvider
from backend.llm.factory import get_llm_provider
from backend.llm.adapters.openai_compatible import OpenAICompatibleAdapter
from backend.llm.adapters.anthropic import AnthropicAdapter
from backend.llm.adapters.gemini import GeminiAdapter
from backend.llm.structured import strip_markdown_fences, parse_and_validate_json
from backend.pipeline.chunker import ProcessExtractor
from backend.ir.models import ProcessIR, FlowNode, SequenceFlow, Pool, Lane


class MockLLMProvider(LLMProvider):
    def __init__(self, canned_response: str):
        self.canned_response = canned_response
        self.call_count = 0

    def complete(self, messages, json_schema=None, temperature=0.1, max_tokens=4096):
        self.call_count += 1
        return None, self.canned_response, {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150}


class TestPhase2(unittest.TestCase):

    def test_vtt_srt_cleaner(self):
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:04.200
<v Alice>Hello, let's walk through the procurement workflow.</v>

00:00:05.100 --> 00:00:08.500
<v Bob>First the engineer files a purchase requisition.</v>
"""
        cleaned = clean_vtt_srt(vtt_content)
        self.assertNotIn("WEBVTT", cleaned)
        self.assertNotIn("-->", cleaned)
        self.assertIn("Alice: Hello", cleaned)
        self.assertIn("Bob: First the engineer", cleaned)

    def test_csv_ingestion_and_column_detection(self):
        csv_text = """Step ID,Department Actor,Activity Description,Next Step,Branch Condition
1,Customer,Submit Order,2,
2,Finance,Credit Check,3,Credit > 500
3,Warehouse,Pack Items,,
"""
        text_out, rows = parse_csv_content(csv_text)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["actor_role"], "Customer")
        self.assertEqual(rows[0]["step_name"], "Submit Order")
        self.assertEqual(rows[1]["condition"], "Credit > 500")

    def test_docx_ingestion(self):
        import docx
        doc = docx.Document()
        doc.add_heading("Standard Operating Procedure", level=1)
        doc.add_paragraph("Step 1: The operator logs into the portal.")
        doc.add_paragraph("Step 2: The system verifies credentials.")
        
        bio = io.BytesIO()
        doc.save(bio)
        data = bio.getvalue()

        text, tables = parse_docx_bytes(data)
        self.assertIn("Standard Operating Procedure", text)
        self.assertIn("operator logs into the portal", text)

    def test_llm_factory(self):
        openai_p = get_llm_provider("openai_compatible")
        self.assertIsInstance(openai_p, OpenAICompatibleAdapter)

        anthropic_p = get_llm_provider("anthropic")
        self.assertIsInstance(anthropic_p, AnthropicAdapter)

        gemini_p = get_llm_provider("gemini")
        self.assertIsInstance(gemini_p, GeminiAdapter)

    def test_strip_markdown_fences(self):
        wrapped = "```json\n{\"id\": \"Process_1\", \"name\": \"Test\"}\n```"
        self.assertEqual(strip_markdown_fences(wrapped), '{"id": "Process_1", "name": "Test"}')

        raw_surrounded = "Here is the extracted BPMN process:\n{\"id\": \"Process_2\"}\nHope this helps!"
        self.assertEqual(strip_markdown_fences(raw_surrounded), '{"id": "Process_2"}')

    def test_parse_and_validate_json(self):
        valid_json = """{
            "id": "TestProc",
            "name": "Testing Process",
            "elements": [
                {"id": "Start_1", "type": "startEvent", "name": "Start", "laneId": "Lane_1"}
            ],
            "flows": []
        }"""
        instance, error = parse_and_validate_json(valid_json)
        self.assertIsNone(error)
        self.assertIsNotNone(instance)
        self.assertEqual(instance.id, "TestProc")
        self.assertEqual(len(instance.elements), 1)

    def test_chunker_text_split(self):
        extractor = ProcessExtractor(provider=MockLLMProvider("{}"))
        long_text = "\n\n".join([f"Paragraph {i}: Step description detailing the business activity." for i in range(100)])
        chunks = extractor.chunk_text(long_text, max_chunk_tokens=100)
        self.assertGreater(len(chunks), 1, "Should split long text into multiple chunks")


if __name__ == "__main__":
    unittest.main()
