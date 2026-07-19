"""API rate limiting (secure-by-default) — implements FASTAPI-LIMITS-001.

Per-IP / per-user throttling to mitigate DoS and bound expensive work (the
CPE/exposure computation and any downstream model spend).

Key strategy: prefer the caller's bearer token, HASHED — never the raw secret
(security spec §0: MUST NOT log/expose secrets). A hashed-token key is stable
per-user across IPs and works behind reverse proxies, where per-IP keys are
unreliable (FASTAPI-PROXY-001). Anonymous callers fall back to client IP.
"""
import hashlib
import logging

from slowapi import Limiter
from slowapi.middleware import (
    SlowAPIMiddleware,
    _find_route_handler,
    _should_exempt,
    sync_check_limits,
)
from slowapi.util import get_remote_address
from starlette.requests import Request

from backend.config import get_settings

log = logging.getLogger(__name__)


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


class ResilientSlowAPIMiddleware(SlowAPIMiddleware):
    """SlowAPIMiddleware that TRULY fails open when the limiter store is unreachable.

    swallow_errors=True is meant to keep the API up if Redis hiccups, but upstream
    slowapi (0.1.10) still injects rate-limit headers from
    request.state.view_rate_limit afterward - and on a swallowed storage error that
    attribute is never set, so EVERY undecorated route raises
    `AttributeError: 'State' object has no attribute 'view_rate_limit'` -> 500.
    A Redis blip would then take down the whole API, the opposite of fail-open (and
    it is why the backend test suite 500s in CI, which has no Redis).

    We mirror the upstream dispatch but (a) fail open if the limit check itself
    raises and (b) only inject headers when the limit actually evaluated. Decorated
    (@limiter.limit) and exempt (@limiter.exempt) routes are handled exactly as
    upstream - this only changes the swallowed-error path.
    """

    async def dispatch(self, request: Request, call_next):
        app = request.app
        limiter_ = app.state.limiter
        if not limiter_.enabled:
            return await call_next(request)

        handler = _find_route_handler(app.routes, request.scope)
        if _should_exempt(limiter_, handler):
            return await call_next(request)

        try:
            error_response, should_inject_headers = sync_check_limits(
                limiter_, request, handler, app
            )
        except Exception as exc:  # storage/eval blew up -> serve unthrottled
            log.warning("rate limit check failed; serving request unthrottled: %s", exc)
            return await call_next(request)

        if error_response is not None:  # a real 429 - honor it
            return error_response

        response = await call_next(request)
        # Inject headers ONLY if the limit evaluated (view_rate_limit is set). When
        # the store hiccuped and slowapi swallowed it, the attribute is absent;
        # injecting would 500 the response, so we skip it - fail open.
        if should_inject_headers and hasattr(request.state, "view_rate_limit"):
            try:
                response = limiter_._inject_headers(response, request.state.view_rate_limit)
            except Exception as exc:  # never let header decoration break the response
                log.warning("rate limit header injection failed: %s", exc)
        return response
