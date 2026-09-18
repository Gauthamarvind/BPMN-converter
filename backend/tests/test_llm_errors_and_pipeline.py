"""
Unit tests for Custom LLM Exceptions, Structured Output Logging/Self-Healing,
and Process Pipeline strict error handling without silent fallbacks.
"""

import sys
import unittest
import logging
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.llm.errors import (
    LLMError,
    LLMConnectionError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMResponseError,
    LLMEmptyResponseError,
    LLMValidationError,
    LLMContextLengthExceededError,
    LLMConfigurationError,
)
from backend.llm.base import LLMProvider
from backend.llm.structured import (
    strip_markdown_fences,
    parse_and_validate_json,
    extract_with_self_healing,
)
from backend.pipeline.process_pipeline import process_pipeline
from backend.ir.models import ProcessIR


class FailingMockLLMProvider(LLMProvider):
    def __init__(self, mode: str = "invalid_json"):
        self.mode = mode
        self.attempts = 0

    def complete(self, messages, json_schema=None, temperature=0.1, max_tokens=4096):
        self.attempts += 1
        if self.mode == "invalid_json":
            return None, "{ this is invalid json }", {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
        elif self.mode == "auth_error":
            return None, "401 Unauthorized: Invalid API key provided", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        elif self.mode == "rate_limit":
            return None, "429 Too Many Requests: Rate limit exceeded", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        elif self.mode == "connection_error":
            return None, "Connection refused by host", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        elif self.mode == "api_error":
            return None, "API error: Internal server error 500", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        elif self.mode == "heal_on_attempt_2":
            if self.attempts == 1:
                return None, "{ bad json }", {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
            else:
                valid_json = '{"id": "Proc1", "name": "Healed Process", "elements": [{"id": "S1", "type": "startEvent", "name": "Start"}], "flows": []}'
                return None, valid_json, {"prompt_tokens": 15, "completion_tokens": 25, "total_tokens": 40}
        return None, "", {}


class TestLLMErrorsAndStructured(unittest.TestCase):

    def test_exception_hierarchy(self):
        self.assertTrue(issubclass(LLMConnectionError, LLMError))
        self.assertTrue(issubclass(LLMAuthenticationError, LLMError))
        self.assertTrue(issubclass(LLMRateLimitError, LLMError))
        self.assertTrue(issubclass(LLMResponseError, LLMError))
        self.assertTrue(issubclass(LLMEmptyResponseError, LLMError))
        self.assertTrue(issubclass(LLMValidationError, LLMError))
        self.assertTrue(issubclass(LLMValidationError, ValueError))
        self.assertTrue(issubclass(LLMContextLengthExceededError, LLMError))
        self.assertTrue(issubclass(LLMConfigurationError, LLMError))

    def test_validation_error_attributes(self):
        err = LLMValidationError(
            message="Validation failed",
            last_raw_output="{ invalid }",
            attempts=3,
            last_error="JSON syntax error",
            details={"field": "elements"}
        )
        self.assertEqual(err.attempts, 3)
        self.assertEqual(err.last_raw_output, "{ invalid }")
        self.assertEqual(err.last_error, "JSON syntax error")
        self.assertIn("details={'field': 'elements'}", str(err))

    def test_structured_logging_and_auth_error(self):
        prov = FailingMockLLMProvider(mode="auth_error")
        prompts_dir = _PROJECT_ROOT / "prompts"
        
        with self.assertRaises(LLMAuthenticationError):
            extract_with_self_healing(prov, "Extract BPMN", prompts_dir=prompts_dir)

    def test_structured_logging_and_rate_limit_error(self):
        prov = FailingMockLLMProvider(mode="rate_limit")
        prompts_dir = _PROJECT_ROOT / "prompts"

        with self.assertRaises(LLMRateLimitError):
            extract_with_self_healing(prov, "Extract BPMN", prompts_dir=prompts_dir)

    def test_structured_logging_and_connection_error(self):
        prov = FailingMockLLMProvider(mode="connection_error")
        prompts_dir = _PROJECT_ROOT / "prompts"

        with self.assertRaises(LLMConnectionError):
            extract_with_self_healing(prov, "Extract BPMN", prompts_dir=prompts_dir)

    def test_structured_logging_and_response_error(self):
        prov = FailingMockLLMProvider(mode="api_error")
        prompts_dir = _PROJECT_ROOT / "prompts"

        with self.assertRaises(LLMResponseError):
            extract_with_self_healing(prov, "Extract BPMN", prompts_dir=prompts_dir)

    def test_structured_validation_exhaustion(self):
        prov = FailingMockLLMProvider(mode="invalid_json")
        prompts_dir = _PROJECT_ROOT / "prompts"

        with self.assertRaises(LLMValidationError) as ctx:
            extract_with_self_healing(prov, "Extract BPMN", prompts_dir=prompts_dir, max_attempts=3)
        
        self.assertEqual(prov.attempts, 3)
        self.assertEqual(ctx.exception.attempts, 3)
        self.assertIn("Failed to generate valid Process IR", str(ctx.exception))

    def test_structured_self_healing_success(self):
        prov = FailingMockLLMProvider(mode="heal_on_attempt_2")
        prompts_dir = _PROJECT_ROOT / "prompts"

        ir, usage = extract_with_self_healing(prov, "Extract BPMN", prompts_dir=prompts_dir, max_attempts=3)
        self.assertEqual(prov.attempts, 2)
        self.assertEqual(ir.name, "Healed Process")
        self.assertEqual(len(ir.elements), 1)
        self.assertEqual(usage["total_tokens"], 60)

    def test_pipeline_strict_llm_error_raising(self):
        """Verify process_pipeline strictly raises errors on LLM failures without silent fallback."""
        with patch("backend.pipeline.process_pipeline.get_llm_provider") as mock_get_prov:
            mock_prov = FailingMockLLMProvider(mode="connection_error")
            mock_get_prov.return_value = mock_prov

            with self.assertRaises(LLMConnectionError):
                process_pipeline(
                    raw_content=b"1. Customer logs in.\n2. Customer places order.",
                    filename="order.txt",
                    mock=False  # non-mock mode
                )

    def test_pipeline_mock_mode_succeeds(self):
        """Verify process_pipeline works cleanly in explicit mock mode."""
        res = process_pipeline(
            raw_content=b"1. Customer logs in.\n2. Customer places order.",
            filename="order.txt",
            mock=True
        )
        self.assertTrue(res["success"])
        self.assertIn("bpmn:definitions", res["bpmn_xml"])
        self.assertEqual(res["metadata"]["extraction"]["mode"], "deterministic_rule_engine")


if __name__ == "__main__":
    unittest.main()
