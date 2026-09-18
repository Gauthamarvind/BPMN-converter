"""
Custom LLM Exceptions for Process2BPMN.
Provides a structured exception hierarchy for transport, auth, rate-limiting, and validation errors.
All exceptions carry provider and model metadata.
"""

from __future__ import annotations
from typing import Optional, Dict, Any


class LLMError(Exception):
    """Base exception for all LLM-related failures."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        kind: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.model = model
        self.details = details or {}
        self.kind = kind or self.__class__.__name__

    def __str__(self) -> str:
        ctx = []
        if self.provider:
            ctx.append(f"provider={self.provider}")
        if self.model:
            ctx.append(f"model={self.model}")
        if self.details:
            ctx.append(f"details={self.details}")
        ctx_str = f" ({', '.join(ctx)})" if ctx else ""
        return f"{self.message}{ctx_str}"


class LLMConnectionError(LLMError):
    """Raised when the LLM service endpoint cannot be reached (DNS, timeout, connection refused)."""
    pass


class LLMAuthenticationError(LLMError):
    """Raised when authentication with the LLM provider fails (invalid/missing API key, 401/403)."""
    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limits or quotas are exceeded (HTTP 429)."""
    pass


class LLMResponseError(LLMError):
    """Raised when the LLM provider returns an HTTP error or unexpected payload structure."""
    pass


class LLMEmptyResponseError(LLMError):
    """Raised when the LLM returns an empty completion."""
    pass


class LLMValidationError(LLMError, ValueError):
    """Raised when LLM output fails schema validation even after self-healing retries."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        last_raw_output: str = "",
        attempts: int = 0,
        last_error: str = "",
        details: Optional[Dict[str, Any]] = None,
        kind: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            details=details,
            kind=kind or "LLMValidationError",
        )
        self.last_raw_output = last_raw_output
        self.attempts = attempts
        self.last_error = last_error


class LLMContextLengthExceededError(LLMError):
    """Raised when prompt + generation exceeds provider context window."""
    pass


class LLMConfigurationError(LLMError):
    """Raised when LLM provider configuration is invalid or missing."""
    pass
