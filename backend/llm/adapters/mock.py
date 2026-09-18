"""
Offline Mock Adapter.

Thin ``LLMProvider`` wrapper around the single deterministic rule engine in
``backend.pipeline.mock_extractor``. It exists so that ``provider=mock`` behaves exactly
like ``mock=true`` everywhere a provider object is required (connection ping, lane
mapping fallback, direct ``ProcessExtractor`` use). The conversion pipeline itself routes
``provider=mock`` straight to the rule engine and never calls ``complete``.

The previous implementation was a second, divergent rule engine that emitted
``sourceRef``/``targetRef`` keys the IR loader does not understand, so every flow was
dropped and every node reported unreachable.
"""

from __future__ import annotations
import json
import re
from typing import List, Dict, Any, Optional, Tuple

from backend.llm.base import LLMProvider


_CHUNK_MARKERS = (
    "## Process Document Fragment",
    "## Input Text",
    "## Process Text",
    "=== Chunk",
)


def _extract_user_text(content: str) -> str:
    """
    Best-effort recovery of the document text from an extraction prompt: everything after
    the last known chunk marker, otherwise the whole prompt. Prompt instructions that
    survive are harmless to the rule engine (it only keys on numbered/bulleted/dialogue lines).
    """
    best = -1
    for marker in _CHUNK_MARKERS:
        idx = content.rfind(marker)
        if idx > best:
            best = idx + len(marker)
    text = content[best:] if best >= 0 else content
    # drop trailing "Return ONLY JSON" style instructions
    text = re.split(r"\n#{1,3}\s*(Required JSON Schema|Output|Return|Response)", text, maxsplit=1)[0]
    return text.strip()


class MockAdapter(LLMProvider):
    """Deterministic, zero-network provider backed by the shared rule engine."""

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        model: str = "mock",
        timeout: float = 90.0,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model or "mock"
        self.timeout = timeout
        self.provider = "mock"
        self.provider_name = "mock"

    def complete(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Tuple[Optional[Dict[str, Any]], str, Dict[str, Any]]:
        from backend.pipeline.mock_extractor import generate_mock_ir_from_text

        user_content = "\n".join(m.get("content", "") for m in messages if m.get("role") == "user")

        # Tiny prompts (e.g. the connection ping) get a tiny answer, not a whole process.
        if len(user_content.strip()) < 80 and "json" not in user_content.lower():
            return None, "OK", {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5}

        ir = generate_mock_ir_from_text(_extract_user_text(user_content))
        ir_dict = ir.to_dict()
        raw_text = json.dumps(ir_dict, indent=2)
        usage = {
            "prompt_tokens": max(10, len(user_content) // 4),
            "completion_tokens": max(20, len(raw_text) // 4),
            "total_tokens": max(30, (len(user_content) + len(raw_text)) // 4),
        }
        return ir_dict, raw_text, usage
