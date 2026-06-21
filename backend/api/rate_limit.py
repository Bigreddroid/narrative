"""API rate limiting (secure-by-default) — implements FASTAPI-LIMITS-001.

Per-IP / per-user throttling to mitigate DoS and bound expensive work (the
CPE/exposure computation and any downstream model spend).

Key strategy: prefer the caller's bearer token, HASHED — never the raw secret
(security spec §0: MUST NOT log/expose secrets). A hashed-token key is stable
per-user across IPs and works behind reverse proxies, where per-IP keys are
unreliable (FASTAPI-PROXY-001). Anonymous callers fall back to client IP.
"""
import hashlib

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from backend.config import get_settings


def rate_limit_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer " and auth[7:].strip():
        token = auth[7:].strip()
        # Hash the token → stable per-user key that never exposes the secret.
        return "tok:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
    return "ip:" + get_remote_address(request)


# Shared Redis store so limits are EXACT across multiple Gunicorn workers (the
# prod API runs --workers 2). Falls back to in-process memory if no Redis URL is
# configured. swallow_errors keeps the API available if the store ever hiccups —
# a rate limiter must never become its own outage (fail-open).
_redis_url = str(getattr(get_settings(), "redis_url", "") or "")
_storage_uri = _redis_url if _redis_url.startswith("redis") else "memory://"

limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=["120/minute"],
    storage_uri=_storage_uri,
    swallow_errors=True,
)
