"""
Abstract LLM Provider Interface.
Standardizes completion across all LLM vendors.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class LLMProvider(ABC):
    """
    Vendor-agnostic LLM interface.
    Each provider adapter implements `complete`.
    """

    @abstractmethod
    def complete(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Tuple[Optional[Dict[str, Any]], str, Dict[str, Any]]:
        """
        Executes a completion request.
        
        Args:
            messages: List of message dicts [{"role": "user"|"system"|"assistant", "content": "..."}]
            json_schema: Optional JSON Schema to guide or enforce structured output
            temperature: Sampling temperature
            max_tokens: Maximum tokens in completion

        Returns:
            Tuple of:
            - parsed_json: Optional[Dict[str, Any]] - Extracted JSON if present, else None
            - raw_text: str - Raw response text from the model
            - usage: Dict[str, Any] - Token usage metrics (prompt_tokens, completion_tokens, total_tokens)
        """
        pass
