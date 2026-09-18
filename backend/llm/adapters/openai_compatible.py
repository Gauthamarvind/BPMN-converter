"""
OpenAI-Compatible LLM Adapter.
Covers OpenAI, Azure OpenAI, Ollama, vLLM, LM Studio, Groq, Mistral, and OpenRouter.
Works fully offline with Ollama by default.
"""

from __future__ import annotations
import json
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional, Tuple

from backend.config import config
from backend.llm.base import LLMProvider
from backend.llm.structured import strip_markdown_fences
from backend.llm.adapters._http import post_json


def normalize_chat_endpoint(base_url: str) -> str:
    """
    Normalizes base_url according to URL structure:
    - No path -> append /v1/chat/completions
    - Path ending in /v1 -> append /chat/completions
    - Path ending in /chat/completions (Azure) -> unchanged
    - Other path -> append /chat/completions
    """
    url = base_url.strip().rstrip("/")
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path or path == "":
        return f"{url}/v1/chat/completions"
    elif path.endswith("/v1"):
        return f"{url}/chat/completions"
    elif path.endswith("/chat/completions"):
        return url
    else:
        return f"{url}/chat/completions"


class OpenAICompatibleAdapter(LLMProvider):
    """
    Adapter for any OpenAI-compatible chat completions endpoint.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
        model: str = "llama3",
        timeout: float = 90.0,
        auth_header: Optional[str] = None,
    ):
        self.endpoint = normalize_chat_endpoint(base_url)
        self.api_key = api_key or "dummy"
        self.model = model
        self.timeout = timeout
        self.auth_header = auth_header or getattr(config.llm, "auth_header", "Authorization")
        self.provider = "openai_compatible"

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.auth_header.lower() == "authorization":
            headers[self.auth_header] = f"Bearer {self.api_key}"
        else:
            headers[self.auth_header] = self.api_key
        return headers

    def complete(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Tuple[Optional[Dict[str, Any]], str, Dict[str, Any]]:
        headers = self._build_headers()

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        data = post_json(
            endpoint=self.endpoint,
            headers=headers,
            payload=payload,
            timeout=self.timeout,
            provider=self.provider,
            model=self.model,
        )

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
