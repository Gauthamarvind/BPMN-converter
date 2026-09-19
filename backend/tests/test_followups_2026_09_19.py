"""
Regression tests for the 2026-09-19 follow-ups:
- LLM_TIMEOUT is read from config and handed to every adapter by the factory.
- OpenAICompatibleAdapter enables JSON mode when a schema is supplied and falls back cleanly
  when the server rejects `response_format`.
- extract_with_self_healing forwards the ProcessIR schema to the provider.
- The Celonis profile differs from generic in more than maxLabelLength.
"""

from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.config import config
from backend.llm.errors import LLMResponseError
from backend.llm.adapters import openai_compatible as oc
from backend.llm.adapters.openai_compatible import OpenAICompatibleAdapter


def _ok_response(text: str = '{"ok": true}'):
    return {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class TestTimeoutWiring:
    def test_config_exposes_timeout_with_default(self):
        assert hasattr(config.llm, "timeout")
        assert float(config.llm.timeout) > 0

    def test_factory_passes_timeout_to_openai_compatible(self, monkeypatch):
        from backend.llm import factory
        monkeypatch.setattr(config.llm, "timeout", 321.0)
        adapter = factory.get_llm_provider("ollama", base_url="http://localhost:11434/v1", api_key="x", model="m")
        assert isinstance(adapter, OpenAICompatibleAdapter)
        assert adapter.timeout == 321.0

    def test_factory_passes_timeout_to_mock(self, monkeypatch):
        from backend.llm import factory
        monkeypatch.setattr(config.llm, "timeout", 12.5)
        adapter = factory.get_llm_provider("mock")
        assert adapter.timeout == 12.5


class TestJsonMode:
    def test_response_format_sent_when_schema_given(self):
        adapter = OpenAICompatibleAdapter(base_url="http://localhost:11434/v1", api_key="k", model="m")
        captured = {}

        def fake_post(endpoint, headers, payload, timeout, provider, model):
            captured["payload"] = payload
            return _ok_response()

        with patch.object(oc, "post_json", side_effect=fake_post):
            parsed, raw, usage = adapter.complete(
                messages=[{"role": "user", "content": "Return JSON"}],
                json_schema={"type": "object"},
            )
        assert captured["payload"]["response_format"] == {"type": "json_object"}
        assert parsed == {"ok": True}
        assert usage["total_tokens"] == 2

    def test_no_response_format_without_schema(self):
        adapter = OpenAICompatibleAdapter(base_url="http://localhost:11434/v1", api_key="k", model="m")
        captured = {}

        def fake_post(endpoint, headers, payload, timeout, provider, model):
            captured["payload"] = payload
            return _ok_response("pong")

        with patch.object(oc, "post_json", side_effect=fake_post):
            adapter.complete(messages=[{"role": "user", "content": "ping"}])
        assert "response_format" not in captured["payload"]

    def test_falls_back_when_server_rejects_response_format(self):
        adapter = OpenAICompatibleAdapter(base_url="http://localhost:8001/v1", api_key="k", model="m")
        payloads = []

        def fake_post(endpoint, headers, payload, timeout, provider, model):
            payloads.append(dict(payload))
            if "response_format" in payload:
                raise LLMResponseError(
                    "HTTP 400 error from openai_compatible: unknown field response_format",
                    provider=provider,
                    model=model,
                    details={"status_code": 400, "body": "unknown field response_format"},
                )
            return _ok_response()

        with patch.object(oc, "post_json", side_effect=fake_post):
            parsed, _, _ = adapter.complete(
                messages=[{"role": "user", "content": "Return JSON"}],
                json_schema={"type": "object"},
            )
        assert len(payloads) == 2
        assert "response_format" in payloads[0]
        assert "response_format" not in payloads[1]
        assert parsed == {"ok": True}

    def test_other_400s_are_not_retried(self):
        adapter = OpenAICompatibleAdapter(base_url="http://localhost:8001/v1", api_key="k", model="m")
        calls = []

        def fake_post(endpoint, headers, payload, timeout, provider, model):
            calls.append(1)
            raise LLMResponseError(
                "HTTP 400 error: model not found",
                provider=provider,
                model=model,
                details={"status_code": 400, "body": "model not found"},
            )

        with patch.object(oc, "post_json", side_effect=fake_post):
            with pytest.raises(LLMResponseError):
                adapter.complete(
                    messages=[{"role": "user", "content": "Return JSON"}],
                    json_schema={"type": "object"},
                )
        assert len(calls) == 1


class TestSchemaForwarded:
    def test_extractor_passes_schema_to_provider(self):
        from backend.llm.structured import extract_with_self_healing
        from backend.llm.base import LLMProvider

        seen = {}

        class SpyProvider(LLMProvider):
            provider = "spy"
            model = "spy"

            def complete(self, messages, json_schema=None, temperature=0.1, max_tokens=4096):
                seen["schema"] = json_schema
                # Deliberately invalid so the loop exits via the validation error path.
                return None, "not json", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        with pytest.raises(Exception):
            extract_with_self_healing(
                provider=SpyProvider(),
                prompt="Return the process as JSON.",
                prompts_dir=_PROJECT_ROOT / "prompts",
                max_attempts=1,
            )
        assert isinstance(seen.get("schema"), dict)
        assert "properties" in seen["schema"]


class TestCelonisProfile:
    def test_celonis_differs_from_generic_beyond_label_length(self):
        from backend.pipeline.linter import ProfileLinter
        linter = ProfileLinter()
        celonis = linter.load_profile("celonis")
        generic = linter.load_profile("generic")
        assert celonis["maxLabelLength"] != generic["maxLabelLength"]
        assert celonis["conditionLocation"] == "both"
        assert generic["conditionLocation"] == "conditionExpression"
        assert "callActivity" in generic["allowedElementTypes"]
        assert "callActivity" not in celonis["allowedElementTypes"]
