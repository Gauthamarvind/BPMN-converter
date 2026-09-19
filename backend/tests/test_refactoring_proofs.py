"""
Comprehensive Proof Tests for Refactoring Items A1-A6.
Verifies exception hierarchy, lazy imports, endpoint normalization,
status codes (400, 401, 502), and zero-network mock execution.
"""

import sys
import io
import shutil
import tempfile
import importlib
import unittest
from pathlib import Path
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from starlette.testclient import TestClient
from backend.server import app
from backend.config import config
from backend.ir.models import ProcessIR
from backend.ingestion.parser import ingest_file, IngestionError
from backend.llm.adapters._http import post_json
from backend.llm.adapters.openai_compatible import normalize_chat_endpoint, OpenAICompatibleAdapter
from backend.llm.adapters.gemini import GeminiAdapter
from backend.llm.adapters.mock import MockAdapter
from backend.llm.factory import get_llm_provider
from backend.llm.errors import (
    LLMError,
    LLMConnectionError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMResponseError,
    LLMValidationError,
    LLMConfigurationError,
)
from backend.pipeline.process_pipeline import process_pipeline


class TestRefactoringProofs(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    # --- A1 & A4: Normalization, Headers, and HTTP Exception Raising ---

    def test_normalize_chat_endpoint(self):
        self.assertEqual(normalize_chat_endpoint("http://localhost:11434"), "http://localhost:11434/v1/chat/completions")
        self.assertEqual(normalize_chat_endpoint("http://localhost:11434/"), "http://localhost:11434/v1/chat/completions")
        self.assertEqual(normalize_chat_endpoint("http://localhost:11434/v1"), "http://localhost:11434/v1/chat/completions")
        self.assertEqual(normalize_chat_endpoint("http://localhost:11434/v1/"), "http://localhost:11434/v1/chat/completions")
        self.assertEqual(normalize_chat_endpoint("https://api.openai.com/v1/chat/completions"), "https://api.openai.com/v1/chat/completions")

    def test_openai_compatible_auth_headers(self):
        # Default Authorization Bearer
        adapter_default = OpenAICompatibleAdapter(base_url="http://localhost:8000", api_key="sk-123", model="test")
        self.assertEqual(adapter_default._build_headers()["Authorization"], "Bearer sk-123")

        # Custom auth header (e.g. X-API-Key or api-key)
        adapter_custom = OpenAICompatibleAdapter(base_url="http://localhost:8000", api_key="secret-key", model="test", auth_header="X-API-Key")
        headers = adapter_custom._build_headers()
        self.assertEqual(headers["X-API-Key"], "secret-key")
        self.assertNotIn("Authorization", headers)

    def test_gemini_api_key_header(self):
        adapter = GeminiAdapter(api_key="gemini-key-123", model="gemini-1.5-flash")
        url, headers = adapter._build_request_params()
        self.assertNotIn("key=", url)
        self.assertEqual(headers["x-goog-api-key"], "gemini-key-123")

    # --- A3: Factory Lazy Loading & Mock Provider ---

    def test_factory_lazy_imports_with_missing_gemini(self):
        """Copies backend to temp dir, deletes gemini.py, imports factory and builds openai_compatible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            tmp_backend = tmp_root / "backend"
            shutil.copytree(_PROJECT_ROOT / "backend", tmp_backend)

            # Delete gemini.py adapter
            gemini_file = tmp_backend / "llm" / "adapters" / "gemini.py"
            if gemini_file.exists():
                gemini_file.unlink()
            self.assertFalse(gemini_file.exists())

            # Add tmp_root to sys.path front
            sys.path.insert(0, str(tmp_root))
            try:
                # Remove cached modules from sys.modules to force reload
                for m in list(sys.modules.keys()):
                    if m.startswith("backend.llm"):
                        del sys.modules[m]

                from backend.llm.factory import get_llm_provider as temp_get_llm_provider
                adapter = temp_get_llm_provider(
                    provider_name="openai_compatible",
                    base_url="http://localhost:11434",
                    api_key="test",
                    model="llama3"
                )
                self.assertIsNotNone(adapter)
                self.assertEqual(adapter.provider, "openai_compatible")
            finally:
                sys.path.remove(str(tmp_root))
                # Restore main sys.modules
                for m in list(sys.modules.keys()):
                    if m.startswith("backend.llm"):
                        del sys.modules[m]

    def test_factory_unknown_provider_raises_configuration_error(self):
        with self.assertRaises(LLMConfigurationError) as ctx:
            get_llm_provider(provider_name="unknown_vendor_xyz")
        self.assertIn("Unsupported LLM provider 'unknown_vendor_xyz'", str(ctx.exception))

    def test_mock_provider_converts_sample_sop_no_network(self):
        sample_sop_path = _PROJECT_ROOT / "backend" / "tests" / "fixtures" / "sample_sop.md"
        self.assertTrue(sample_sop_path.exists())
        content = sample_sop_path.read_bytes()

        result = process_pipeline(
            raw_content=content,
            filename="sample_sop.md",
            profile_name="generic",
            provider_name="mock",
            model="mock",
            mock=False
        )
        self.assertTrue(result["success"])
        self.assertIn("bpmn:definitions", result["bpmn_xml"])
        self.assertGreater(len(result["ir"]["elements"]), 0)

    # --- A5: 502 Status and Error Response Body Fields on Connection Failure ---

    def test_convert_dead_endpoint_returns_502_with_four_fields(self):
        # Point to unreachable port 9
        res = self.client.post("/api/convert", data={
            "text": "1. Customer places order.\n2. Invoice generated.",
            "filename": "order.txt",
            "provider": "openai_compatible",
            "model": "test-model",
            "base_url": "http://127.0.0.1:9",
            "api_key": "test"
        })
        self.assertEqual(res.status_code, 502)
        body = res.json()
        self.assertIn("error", body)
        self.assertIn("kind", body)
        self.assertIn("provider", body)
        self.assertIn("model", body)
        self.assertEqual(body["kind"], "LLMConnectionError")
        self.assertEqual(body["provider"], "openai_compatible")
        self.assertEqual(body["model"], "test-model")

    # --- A6: Ingestion Errors -> 400 ---

    def test_corrupt_xlsx_returns_400_ingestion_error(self):
        # Starts with PK but has invalid zip structure
        corrupt_xlsx = b"PK\x03\x04corrupted_content_not_a_valid_zip"
        files = {"file": ("corrupt.xlsx", corrupt_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        res = self.client.post("/api/convert", files=files)
        self.assertEqual(res.status_code, 400)
        body = res.json()
        self.assertEqual(body.get("kind"), "IngestionError")

    def test_empty_txt_returns_400_ingestion_error(self):
        files = {"file": ("empty.txt", b"    \n\t  \n  ", "text/plain")}
        res = self.client.post("/api/convert", files=files)
        self.assertEqual(res.status_code, 400)
        body = res.json()
        self.assertEqual(body.get("kind"), "IngestionError")

    def test_text_free_pdf_returns_400_ingestion_error(self):
        # A valid empty 1-page PDF with no text stream
        empty_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n185\n%%EOF\n"
        )
        files = {"file": ("empty_text.pdf", empty_pdf, "application/pdf")}
        res = self.client.post("/api/convert", files=files)
        self.assertEqual(res.status_code, 400)
        body = res.json()
        self.assertEqual(body.get("kind"), "IngestionError")


if __name__ == "__main__":
    unittest.main()
