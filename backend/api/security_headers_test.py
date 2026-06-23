"""Asserts the security-headers middleware is applied. Run from repo root:
    python -m backend.api.security_headers_test

Hits /health via TestClient (DB-free, rate-limit-exempt), so it runs in CI
without Postgres/Redis.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

from backend.main import app

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


with TestClient(app) as client:
    r = client.get("/health")
    ok("health still 200", r.status_code == 200)
    h = r.headers
    ok("X-Content-Type-Options: nosniff", h.get("x-content-type-options") == "nosniff")
    ok("X-Frame-Options: DENY", h.get("x-frame-options") == "DENY")
    ok("Referrer-Policy: no-referrer", h.get("referrer-policy") == "no-referrer")
    ok("X-XSS-Protection: 0", h.get("x-xss-protection") == "0")
    # Note: the uvicorn "server" banner is suppressed at the server layer
    # (--no-server-header in the run scripts), not in middleware — a middleware
    # override only appends a duplicate header, so we don't assert on it here.

print(f"\nsecurity_headers: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
