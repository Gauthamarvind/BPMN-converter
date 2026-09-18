"""
Anthropic Messages API Adapter.
Supports Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku.
"""

from __future__ import annotations
import json
import httpx
from typing import List, Dict, Any, Optional, Tuple
from backend.llm.base import LLMProvider
from backend.llm.structured import strip_markdown_fences


class AnthropicAdapter(LLMProvider):
    """
    Adapter for Anthropic /v1/messages API.
    """

    def __init__(
        self,
        base_url: str = "https://api.anthropic.com/v1",
        api_key: str = "",
        model: str = "claude-3-5-sonnet-20241022",
        timeout: float = 90.0,
    ):
        cleaned_url = base_url.rstrip("/")
        if not cleaned_url.endswith("/messages"):
            cleaned_url = f"{cleaned_url}/messages"
        self.endpoint = cleaned_url
        self.api_key = api_key
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
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        # Separate system messages from user/assistant messages for Anthropic
        system_content = ""
        user_assistant_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_content += f"{m.get('content', '')}\n"
            else:
                user_assistant_messages.append({
                    "role": m.get("role", "user"),
                    "content": m.get("content", "")
                })

        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": user_assistant_messages,
        }
        if system_content.strip():
            payload["system"] = system_content.strip()

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(self.endpoint, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            # Anthropic response: {content: [{type: 'text', text: '...'}]}
            content_blocks = data.get("content", [])
            raw_text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text").strip()

            usage_info = data.get("usage", {})
            usage = {
                "prompt_tokens": usage_info.get("input_tokens", 0),
                "completion_tokens": usage_info.get("output_tokens", 0),
                "total_tokens": usage_info.get("input_tokens", 0) + usage_info.get("output_tokens", 0),
            }

            parsed_json = None
            cleaned = strip_markdown_fences(raw_text)
            try:
                parsed_json = json.loads(cleaned)
            except Exception:
                parsed_json = None

            return parsed_json, raw_text, usage

        except httpx.HTTPError as he:
            err_msg = f"Anthropic API error: {str(he)}"
            return None, err_msg, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        except Exception as ex:
            err_msg = f"Unexpected Anthropic connection error: {str(ex)}"
            return None, err_msg, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
