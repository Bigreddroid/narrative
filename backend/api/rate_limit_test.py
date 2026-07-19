"""Locks the rate limiter's FAIL-OPEN contract. Run from repo root:
    python -m backend.api.rate_limit_test

Regression for the CI-red bug: with a configured-but-UNREACHABLE Redis store,
slowapi swallows the storage error (swallow_errors=True) but still tries to inject
rate-limit headers from request.state.view_rate_limit - which was never set - so
every UNDECORATED route 500s. That turns a Redis hiccup into a full API outage,
the opposite of the intended fail-open. ResilientSlowAPIMiddleware must serve the
request unthrottled instead. This test needs NO live Redis (the whole point).
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.api.rate_limit import ResilientSlowAPIMiddleware

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


def _app(storage_uri: str) -> FastAPI:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["100/minute"],
        storage_uri=storage_uri,
        swallow_errors=True,
        headers_enabled=True,  # so the healthy path actually injects X-RateLimit-* headers
    )
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(ResilientSlowAPIMiddleware)

    @app.get("/x")  # UNDECORATED -> only the global default_limits apply (the crash path)
    def x():
        return {"ok": True}

    return app


# 1) Dead Redis store -> the route must STILL succeed (fail open), not 500.
with TestClient(_app("redis://localhost:6399/0")) as client:
    r = client.get("/x")
    ok("fails open on unreachable Redis (200, not 500)", r.status_code == 200)
    ok("body served intact when failing open", r.json() == {"ok": True})

# 2) Working (in-memory) store -> normal path intact: 200 + rate-limit headers.
with TestClient(_app("memory://")) as client:
    r = client.get("/x")
    ok("healthy store still 200", r.status_code == 200)
    ok("healthy store injects rate-limit headers",
       any(h.lower() == "x-ratelimit-limit" for h in r.headers))

print(f"\nrate_limit: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
