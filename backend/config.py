"""
Application Configuration.
Reads LLM and pipeline settings strictly from environment variables or .env.
Vendor-agnostic by design.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


from backend.version import VERSION


@dataclass
class LLMConfig:
    provider: str = os.getenv("LLM_PROVIDER", "openai_compatible").lower()
    model: str = os.getenv("LLM_MODEL", "llama3")
    base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    api_key: str = os.getenv("LLM_API_KEY", "ollama")
    auth_header: str = os.getenv("LLM_AUTH_HEADER", "Authorization")
    context_tokens: int = int(os.getenv("LLM_CONTEXT_TOKENS", "8192"))
    max_output_tokens: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "4096"))
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    # Seconds to wait for one completion. Local models (Ollama on CPU) can need far more than
    # the old hard-coded 90s to emit a 4k-token JSON document.
    timeout: float = float(os.getenv("LLM_TIMEOUT", "90"))


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    single_pool: bool = field(default_factory=lambda: os.getenv("SINGLE_POOL", "true").lower() in ("true", "1", "yes"))
    prompts_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "prompts")
    profiles_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "profiles")
    version: str = VERSION



config = AppConfig()
