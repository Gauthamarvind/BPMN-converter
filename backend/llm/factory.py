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


OPENAI_STYLE_DEFAULT_URLS = (
    "http://localhost:11434/v1",
    "http://127.0.0.1:11434/v1",
    "http://localhost:11434",
)


def _is_custom_base_url(url: Optional[str]) -> bool:
    """
    True when the caller deliberately set a base URL for a hosted provider.
    Empty values and the Ollama/OpenAI-compatible default are not custom: they leak in
    from the generic LLM_BASE_URL default or from a stale UI field and must not be applied
    to Gemini or Anthropic, whose adapters have their own correct defaults.
    """
    cleaned = (url or "").strip().rstrip("/")
    return bool(cleaned) and cleaned not in OPENAI_STYLE_DEFAULT_URLS


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
    timeout = float(getattr(config.llm, "timeout", 90.0) or 90.0)

    if prov in ("openai", "openai_compatible", "ollama", "vllm", "lmstudio", "groq", "mistral", "openrouter"):
        from backend.llm.adapters.openai_compatible import OpenAICompatibleAdapter
        return OpenAICompatibleAdapter(base_url=url, api_key=key, model=mdl, auth_header=header, timeout=timeout)
    elif prov in ("anthropic", "claude"):
        from backend.llm.adapters.anthropic import AnthropicAdapter
        kwargs = {"api_key": key, "model": mdl, "timeout": timeout}
        if _is_custom_base_url(url):
            kwargs["base_url"] = url
        return AnthropicAdapter(**kwargs)
    elif prov in ("gemini", "google"):
        try:
            from backend.llm.adapters.gemini import GeminiAdapter
        except ImportError as ex:
            raise LLMConfigurationError(
                "LLM_PROVIDER=gemini but the optional adapter backend/llm/adapters/gemini.py is not "
                "installed. Restore the file or choose another provider."
            ) from ex
        kwargs = {"api_key": key, "model": mdl, "timeout": timeout}
        if _is_custom_base_url(url):
            kwargs["base_url"] = url
        return GeminiAdapter(**kwargs)
    elif prov == "mock":
        from backend.llm.adapters.mock import MockAdapter
        return MockAdapter(base_url=url, api_key=key, model=mdl, timeout=timeout)
    else:
        raise LLMConfigurationError(
            f"Unsupported LLM provider '{prov}'. Supported providers: openai_compatible, anthropic, gemini, mock.",
            provider=prov,
            model=mdl,
        )
