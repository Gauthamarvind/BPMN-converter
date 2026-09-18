"""
Shared HTTP client helper for LLM adapters.
Translates HTTP transport failures, status codes, and non-JSON payloads into typed LLMErrors.
"""

from __future__ import annotations
import json
from typing import Dict, Any
import httpx

from backend.llm.errors import (
    LLMConnectionError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMResponseError,
)


def post_json(
    endpoint: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout: float,
    provider: str,
    model: str,
) -> Dict[str, Any]:
    """
    Executes a POST request to an LLM endpoint and parses JSON response.
    Raises domain LLMErrors with provider and model context on transport, auth, rate limit, or status failures.
    """
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(endpoint, headers=headers, json=payload)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as ex:
        raise LLMConnectionError(
            f"Failed to connect to {provider} ({endpoint}): {str(ex)}",
            provider=provider,
            model=model,
        ) from ex
    except Exception as ex:
        raise LLMConnectionError(
            f"Unexpected network error communicating with {provider} ({endpoint}): {str(ex)}",
            provider=provider,
            model=model,
        ) from ex

    status = resp.status_code

    if status in (401, 403):
        raise LLMAuthenticationError(
            f"Authentication failed for {provider} (HTTP {status}): {resp.text}",
            provider=provider,
            model=model,
            details={"status_code": status, "body": resp.text},
        )
    elif status == 429:
        raise LLMRateLimitError(
            f"Rate limit / quota exceeded for {provider} (HTTP 429): {resp.text}",
            provider=provider,
            model=model,
            details={"status_code": 429, "body": resp.text},
        )
    elif status >= 400:
        raise LLMResponseError(
            f"HTTP {status} error from {provider}: {resp.text}",
            provider=provider,
            model=model,
            details={"status_code": status, "body": resp.text},
        )

    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError) as json_ex:
        raise LLMResponseError(
            f"Non-JSON response received from {provider} (HTTP {status}): {resp.text[:500]}",
            provider=provider,
            model=model,
            details={"status_code": status, "body": resp.text[:500]},
        ) from json_ex
