"""
Custom LLM Exceptions for Process2BPMN.
Provides a structured exception hierarchy for transport, auth, rate-limiting, and validation errors.
"""

from __future__ import annotations
from typing import Optional, Dict, Any


class LLMError(Exception):
    """Base exception for all LLM-related failures."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details={self.details})"
        return self.message


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
        last_raw_output: str = "",
        attempts: int = 0,
        last_error: str = "",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.last_raw_output = last_raw_output
        self.attempts = attempts
        self.last_error = last_error


class LLMContextLengthExceededError(LLMError):
    """Raised when prompt + generation exceeds provider context window."""
    pass


class LLMConfigurationError(LLMError):
    """Raised when LLM provider configuration is invalid or missing."""
    pass
