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


def rate_limit_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer " and auth[7:].strip():
        token = auth[7:].strip()
        # Hash the token → stable per-user key that never exposes the secret.
        return "tok:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
    return "ip:" + get_remote_address(request)


# Default in-memory store: correct for a single Uvicorn worker / local dev. For
# EXACT limits across multiple Gunicorn workers in production, point storage_uri
# at the Redis URL. swallow_errors keeps the API available if the store ever
# hiccups — a rate limiter must never become its own outage (fail-open).
limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=["120/minute"],
    swallow_errors=True,
)
