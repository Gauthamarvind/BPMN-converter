"""
Export profile constants — the single source of truth for what Process2BPMN exports to.

Scope v2 narrowed the product to two targets: Celonis (the default) and generic BPMN 2.0.
``SUPPORTED_PROFILES`` is ordered, and that order is what the API and the toolbar present.
"""

from __future__ import annotations

import os
from typing import List

#: Export targets, in presentation order. Celonis first — it is the default.
SUPPORTED_PROFILES: List[str] = ["celonis", "generic"]


def _default_from_env() -> str:
    """``DEFAULT_PROFILE`` may pick the other target; anything unsupported falls back to Celonis."""
    candidate = os.getenv("DEFAULT_PROFILE", "").strip().lower()
    return candidate if candidate in SUPPORTED_PROFILES else SUPPORTED_PROFILES[0]


#: The target used when a caller does not name one.
DEFAULT_PROFILE: str = _default_from_env()


def normalize_profile(profile_name: str | None) -> str:
    """Returns a supported profile id, falling back to the default for None/unknown values."""
    if profile_name in SUPPORTED_PROFILES:
        return profile_name  # type: ignore[return-value]
    return DEFAULT_PROFILE
