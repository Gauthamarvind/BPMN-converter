"""
OpenAI-Compatible LLM Adapter.
Covers OpenAI, Azure OpenAI, Ollama, vLLM, LM Studio, Groq, Mistral, and OpenRouter.
Works fully offline with Ollama by default.
"""

from __future__ import annotations
import json
import httpx
from typing import List, Dict, Any, Optional, Tuple
from backend.llm.base import LLMProvider
from backend.llm.structured import strip_markdown_fences


class OpenAICompatibleAdapter(LLMProvider):
    """
    Adapter for any OpenAI-compatible /v1/chat/completions endpoint.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
        model: str = "llama3",
        timeout: float = 90.0,
    ):
        # Normalize base_url to avoid double slashes or missing /v1
        cleaned_url = base_url.rstrip("/")
        if not cleaned_url.endswith("/v1") and not "/chat/completions" in cleaned_url:
            cleaned_url = f"{cleaned_url}/v1"
        self.endpoint = f"{cleaned_url}/chat/completions"
        self.api_key = api_key or "dummy"
        self.model = model
        self.timeout = timeout

    def complete(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Tuple[Optional[Dict[str, Any]], str, Dict[str, Any]]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Optional JSON mode if supported by endpoint, but app-side validation guarantees correctness
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(self.endpoint, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            choice = data.get("choices", [{}])[0]
            raw_text = choice.get("message", {}).get("content", "").strip()

            usage_info = data.get("usage", {})
            usage = {
                "prompt_tokens": usage_info.get("prompt_tokens", 0),
                "completion_tokens": usage_info.get("completion_tokens", 0),
                "total_tokens": usage_info.get("total_tokens", 0),
            }

            # Parse JSON if possible
            parsed_json = None
            cleaned = strip_markdown_fences(raw_text)
            try:
                parsed_json = json.loads(cleaned)
            except Exception:
                parsed_json = None

            return parsed_json, raw_text, usage

        except httpx.HTTPError as he:
            err_msg = f"OpenAI-Compatible API error: {str(he)}"
            return None, err_msg, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        except Exception as ex:
            err_msg = f"Unexpected connection error: {str(ex)}"
            return None, err_msg, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
