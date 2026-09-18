"""
LLM Provider Factory.
Instantiates the requested provider adapter based on environment variables / config.
"""

from __future__ import annotations
import os
from backend.config import config
from backend.llm.base import LLMProvider
from backend.llm.adapters.openai_compatible import OpenAICompatibleAdapter
from backend.llm.adapters.anthropic import AnthropicAdapter
from backend.llm.adapters.gemini import GeminiAdapter


def get_llm_provider(
    provider_name: str = None,
    base_url: str = None,
    api_key: str = None,
    model: str = None
) -> LLMProvider:
    """
    Creates an LLMProvider instance.
    Defaults to openai_compatible (Ollama/vLLM/OpenAI) using configuration.
    """
    prov = (provider_name or config.llm.provider or "openai_compatible").lower()
    url = base_url or config.llm.base_url
    key = api_key or config.llm.api_key
    mdl = model or config.llm.model

    if prov in ("openai", "openai_compatible", "ollama", "vllm", "lmstudio", "groq", "mistral", "openrouter"):
        return OpenAICompatibleAdapter(base_url=url, api_key=key, model=mdl)
    elif prov in ("anthropic", "claude"):
        return AnthropicAdapter(base_url=url, api_key=key, model=mdl)
    elif prov in ("gemini", "google"):
        return GeminiAdapter(base_url=url, api_key=key, model=mdl)
    else:
        # Default fallback to OpenAI-compatible interface
        return OpenAICompatibleAdapter(base_url=url, api_key=key, model=mdl)
