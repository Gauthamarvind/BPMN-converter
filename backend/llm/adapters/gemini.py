"""
Google Gemini REST Adapter.
Keeps vendor-specific calls isolated to this adapter without contaminating the core application.
Sends the API key in the x-goog-api-key header instead of query parameters.
"""

from __future__ import annotations
import json
from typing import List, Dict, Any, Optional, Tuple

from backend.llm.base import LLMProvider
from backend.llm.structured import strip_markdown_fences
from backend.llm.adapters._http import post_json


class GeminiAdapter(LLMProvider):
    """
    Adapter for Google Gemini REST generateContent API.
    """

    def __init__(
        self,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        api_key: str = "",
        model: str = "gemini-2.5-flash",
        timeout: float = 90.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.provider = "gemini"

    def _build_request_params(self) -> Tuple[str, Dict[str, str]]:
        endpoint = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        return endpoint, headers

    def complete(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Tuple[Optional[Dict[str, Any]], str, Dict[str, Any]]:
        endpoint, headers = self._build_request_params()

        # Convert messages to Gemini contents format
        contents = []
        system_instruction = None

        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            else:
                gemini_role = "user" if role == "user" else "model"
                contents.append({"role": gemini_role, "parts": [{"text": content}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        data = post_json(
            endpoint=endpoint,
            headers=headers,
            payload=payload,
            timeout=self.timeout,
            provider=self.provider,
            model=self.model,
        )

        candidates = data.get("candidates", [])
        raw_text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            raw_text = "".join(p.get("text", "") for p in parts).strip()

        usage_metadata = data.get("usageMetadata", {})
        usage = {
            "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
            "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
            "total_tokens": usage_metadata.get("totalTokenCount", 0),
        }

        parsed_json = None
        cleaned = strip_markdown_fences(raw_text)
        try:
            parsed_json = json.loads(cleaned)
        except Exception:
            parsed_json = None

        return parsed_json, raw_text, usage
