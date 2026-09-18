"""
Multi-user hardening for the Process2BPMN API.

Everything here is configured from environment variables so a single-user laptop setup
keeps working with no configuration, while a shared deployment turns on:

* Authentication  ``APP_AUTH_MODE`` = ``none`` (default) | ``proxy`` | ``token``
    - proxy: trust the identity header set by the reverse proxy in front of the app
      (``APP_AUTH_HEADER``, default ``X-Forwarded-User``; works with oauth2-proxy,
      Cloudflare Access, Traefik ForwardAuth, Nginx auth_request ...). Requests without
      the header are rejected with 401.
    - token: a shared secret in ``APP_API_TOKEN`` sent as ``Authorization: Bearer <token>``
      (or ``X-API-Token``). Identity comes from the optional ``X-User-Id`` header, else
      ``"api"``. Good for CI, the CLI and small teams.
* Tenancy         the resolved identity is attached to ``request.state.user_id`` and used
                  to scope reference templates.
* SSRF guard      client-supplied ``base_url`` values are validated before the server
                  makes any outbound call (``LLM_ALLOW_PRIVATE_BASE_URLS``,
                  ``LLM_BASE_URL_ALLOWLIST``).
* Rate limiting   a small in-memory sliding window per identity/IP on the expensive
                  conversion endpoints (``RATE_LIMIT_PER_MINUTE``, 0 disables).
* Concurrency     ``MAX_CONCURRENT_EXTRACTIONS`` bounds simultaneous model calls.

Nothing here depends on FastAPI beyond Starlette's middleware/request types, so the pure
helpers (``validate_base_url``, ``safe_identifier``, ``RateLimiter``) are unit-testable.
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import threading
import time
from collections import deque
from typing import Deque, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.identity import LOCAL_USER, safe_identifier, slugify  # noqa: F401  (re-exported)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str) -> List[str]:
    raw = os.getenv(name, "")
    return [x.strip() for x in raw.split(",") if x.strip()]


class SecurityConfig:
    """Read once at import; tests can mutate attributes directly."""

    def __init__(self) -> None:
        self.auth_mode: str = (os.getenv("APP_AUTH_MODE", "none") or "none").strip().lower()
        if self.auth_mode not in ("none", "proxy", "token"):
            raise RuntimeError(f"APP_AUTH_MODE must be none|proxy|token, got '{self.auth_mode}'")
        self.auth_header: str = os.getenv("APP_AUTH_HEADER", "X-Forwarded-User")
        self.api_token: str = os.getenv("APP_API_TOKEN", "")
        if self.auth_mode == "token" and not self.api_token:
            raise RuntimeError("APP_AUTH_MODE=token requires APP_API_TOKEN")
        self.user_id_header: str = os.getenv("APP_USER_ID_HEADER", "X-User-Id")

        hosted = self.auth_mode != "none"
        # Local Ollama lives on a private address, so private base URLs are allowed by
        # default only when the app is single-user.
        self.allow_private_base_urls: bool = _env_bool("LLM_ALLOW_PRIVATE_BASE_URLS", not hosted)
        self.base_url_allowlist: List[str] = [h.lower() for h in _env_list("LLM_BASE_URL_ALLOWLIST")]
        self.allow_client_llm_overrides: bool = _env_bool("ALLOW_CLIENT_LLM_OVERRIDES", True)
        self.expose_server_config: bool = _env_bool("EXPOSE_SERVER_CONFIG", not hosted)

        self.rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30" if hosted else "0"))
        self.max_concurrent_extractions: int = max(1, int(os.getenv("MAX_CONCURRENT_EXTRACTIONS", "4")))
        self.extraction_queue_timeout: float = float(os.getenv("EXTRACTION_QUEUE_TIMEOUT_SECONDS", "30"))

        self.cors_origins: List[str] = _env_list("CORS_ALLOW_ORIGINS")

    @property
    def hosted(self) -> bool:
        return self.auth_mode != "none"


security = SecurityConfig()


# ---------------------------------------------------------------------------
# SSRF guard for model endpoints
# ---------------------------------------------------------------------------

_METADATA_HOSTS = {"169.254.169.254", "metadata.google.internal", "metadata", "fd00:ec2::254"}


def _is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def validate_base_url(
    url: Optional[str],
    *,
    allow_private: Optional[bool] = None,
    allowlist: Optional[Iterable[str]] = None,
    resolve: bool = True,
) -> Optional[str]:
    """
    Validates a client-supplied model endpoint before the server connects to it.

    Rejects non-http(s) schemes, credentials in the URL, cloud metadata hosts, and (unless
    ``allow_private``) private / loopback / link-local addresses. When an allowlist is
    configured the host must be on it. Returns the cleaned URL or raises ``ValueError``.
    """
    if url is None or not str(url).strip():
        return None
    url = str(url).strip()
    if allow_private is None:
        allow_private = security.allow_private_base_urls
    allowed = [h.lower() for h in (allowlist if allowlist is not None else security.base_url_allowlist)]

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("base_url must start with http:// or https://")
    if not parsed.hostname:
        raise ValueError("base_url has no host")
    if parsed.username or parsed.password:
        raise ValueError("base_url must not embed credentials")
    host = parsed.hostname.lower()
    if host in _METADATA_HOSTS:
        raise ValueError("base_url points at a cloud metadata service")

    if allowed:
        if host not in allowed and not any(host.endswith("." + a) for a in allowed):
            raise ValueError(f"base_url host '{host}' is not in LLM_BASE_URL_ALLOWLIST")
        return url

    if not allow_private:
        if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".local") or host.endswith(".internal"):
            raise ValueError("base_url must be a public endpoint on this deployment")
        candidates: List[str] = []
        if _is_private_ip(host):
            raise ValueError("base_url must not point at a private or loopback address")
        if resolve:
            try:
                for info in socket.getaddrinfo(host, None):
                    candidates.append(info[4][0])
            except socket.gaierror:
                candidates = []
            for ip in candidates:
                if _is_private_ip(ip):
                    raise ValueError(f"base_url host '{host}' resolves to a private address")
    return url


# ---------------------------------------------------------------------------
# Rate limiting and concurrency
# ---------------------------------------------------------------------------

class RateLimiter:
    """Sliding-window limiter keyed by identity. Thread-safe, in-memory, per process."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, now: Optional[float] = None) -> Tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        if self.per_minute <= 0:
            return True, 0
        now = time.time() if now is None else now
        window_start = now - 60.0
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] < window_start:
                q.popleft()
            if len(q) >= self.per_minute:
                return False, max(1, int(q[0] + 60.0 - now) + 1)
            q.append(now)
            # keep the dict from growing without bound
            if len(self._hits) > 10000:
                for k in [k for k, v in self._hits.items() if not v]:
                    self._hits.pop(k, None)
            return True, 0


class ExtractionSlot:
    """Bounded semaphore around model calls; raises ``BusyError`` instead of queueing forever."""

    class BusyError(Exception):
        pass

    def __init__(self, limit: int, timeout: float) -> None:
        self._sem = threading.BoundedSemaphore(limit)
        self.timeout = timeout

    def __enter__(self) -> "ExtractionSlot":
        if not self._sem.acquire(timeout=self.timeout):
            raise ExtractionSlot.BusyError(
                f"Server is busy: no extraction slot became free within {int(self.timeout)}s. Try again shortly."
            )
        return self

    def __exit__(self, *exc) -> None:
        self._sem.release()


rate_limiter = RateLimiter(security.rate_limit_per_minute)
extraction_slot = ExtractionSlot(security.max_concurrent_extractions, security.extraction_queue_timeout)


# ---------------------------------------------------------------------------
# Identity resolution + middleware
# ---------------------------------------------------------------------------

PUBLIC_PATHS = ("/api/health",)


def resolve_identity(request: Request) -> Optional[str]:
    """Returns the caller's identity or None if the request is not authenticated."""
    mode = security.auth_mode
    if mode == "none":
        return LOCAL_USER
    if mode == "proxy":
        user = request.headers.get(security.auth_header, "").strip()
        return user or None
    if mode == "token":
        auth = request.headers.get("Authorization", "")
        token = ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        token = token or request.headers.get("X-API-Token", "").strip()
        if not token or not _constant_time_eq(token, security.api_token):
            return None
        return request.headers.get(security.user_id_header, "").strip() or "api"
    return None


def _constant_time_eq(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def client_key(request: Request) -> str:
    user = getattr(request.state, "user_id", None)
    if user and user != LOCAL_USER:
        return f"user:{user}"
    fwd = request.headers.get("X-Forwarded-For", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
    return f"ip:{ip}"


class AuthMiddleware(BaseHTTPMiddleware):
    """Rejects unauthenticated ``/api/*`` calls in proxy/token mode and tags every request with its identity."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path not in PUBLIC_PATHS:
            user = resolve_identity(request)
            if user is None:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "Authentication required",
                        "detail": (
                            "Send the identity header set by your reverse proxy"
                            if security.auth_mode == "proxy"
                            else "Send 'Authorization: Bearer <APP_API_TOKEN>'"
                        ),
                        "kind": "AuthenticationRequired",
                    },
                )
            request.state.user_id = user
        else:
            request.state.user_id = resolve_identity(request) or LOCAL_USER
        return await call_next(request)


def current_user(request: Request) -> str:
    return getattr(request.state, "user_id", None) or LOCAL_USER
