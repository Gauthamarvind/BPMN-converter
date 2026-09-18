"""
Dependency-free identity helpers shared by the web layer and the template store.

Kept separate from ``backend.security`` so that modules which only need to sanitise an
identifier (template storage, the CLI) do not import Starlette.
"""

from __future__ import annotations
import re

LOCAL_USER = "local"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def safe_identifier(value: str, what: str = "identifier") -> str:
    """
    Accepts only short, path-safe identifiers (letters, digits, ``_ . -``; no leading dot).
    Used for template ids that become directory names, so ``..`` or ``/`` can never reach
    the filesystem.
    """
    value = (value or "").strip()
    if not _ID_RE.match(value) or value in (".", "..") or ".." in value:
        raise ValueError(f"Invalid {what} '{value}': use letters, digits, '_', '-' or '.' (max 64 chars).")
    return value


def slugify(value: str, fallback: str = "template", max_len: int = 40) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", (value or "").strip()).strip("_").lower()
    return (slug or fallback)[:max_len]
