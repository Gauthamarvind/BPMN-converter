"""
LLM Provider Factory.
Instantiates the requested provider adapter lazily based on environment variables / config.
Allows individual adapter files to be omitted or deleted without breaking other providers.
"""

from __future__ import annotations
from typing import Optional
from backend.config import config
from backend.llm.base import LLMProvider
from backend.llm.errors import LLMConfigurationError


def get_llm_provider(
    provider_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    auth_header: Optional[str] = None,
) -> LLMProvider:
    """
    Creates an LLMProvider instance lazily.
    Raises LLMConfigurationError for unsupported provider names.
    """
    prov = (provider_name or config.llm.provider or "openai_compatible").lower().strip()
    url = base_url or config.llm.base_url
    key = api_key or config.llm.api_key
    mdl = model or config.llm.model
    header = auth_header or getattr(config.llm, "auth_header", "Authorization")

    if prov in ("openai", "openai_compatible", "ollama", "vllm", "lmstudio", "groq", "mistral", "openrouter"):
        from backend.llm.adapters.openai_compatible import OpenAICompatibleAdapter
        return OpenAICompatibleAdapter(base_url=url, api_key=key, model=mdl, auth_header=header)
    elif prov in ("anthropic", "claude"):
        from backend.llm.adapters.anthropic import AnthropicAdapter
        return AnthropicAdapter(base_url=url, api_key=key, model=mdl)
    elif prov in ("gemini", "google"):
        try:
            from backend.llm.adapters.gemini import GeminiAdapter
        except ImportError as ex:
            raise LLMConfigurationError(
                "LLM_PROVIDER=gemini but the optional adapter backend/llm/adapters/gemini.py is not "
                "installed. Restore the file or choose another provider."
            ) from ex
        return GeminiAdapter(base_url=url, api_key=key, model=mdl)
    elif prov == "mock":
        from backend.llm.adapters.mock import MockAdapter
        return MockAdapter(base_url=url, api_key=key, model=mdl)
    else:
        raise LLMConfigurationError(
            f"Unsupported LLM provider '{prov}'. Supported providers: openai_compatible, anthropic, gemini, mock.",
            provider=prov,
            model=mdl,
        )
