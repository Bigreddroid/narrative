"""Property tests for auth primitives (pure, no DB). Run from repo root:
    python -m backend.api.auth_test

Covers the security-critical password hashing/verification and JWT issuance in
backend/api/routes/auth.py. These functions have no DB dependency, so the test
runs in CI without Postgres.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import uuid
from datetime import datetime, timezone

from jose import jwt

from backend.config import get_settings
from backend.models.user import User
from backend.api.routes.auth import (
    PBKDF2_ITERS,
    hash_password,
    verify_password,
    _issue_token,
)

settings = get_settings()
passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# ── hash_password format ─────────────────────────────────────────────────────
h = hash_password("correct horse battery staple")
parts = h.split("$")
ok("hash has 4 $-separated parts", len(parts) == 4)
ok("hash names pbkdf2_sha256 algo", parts[0] == "pbkdf2_sha256")
ok("hash records iteration count", parts[1] == str(PBKDF2_ITERS))
ok("iteration count is 200k (cost guard)", PBKDF2_ITERS == 200_000)
ok("salt is 16 bytes (32 hex chars)", len(parts[2]) == 32)
ok("derived key is 32 bytes (64 hex chars)", len(parts[3]) == 64)

# ── verify_password roundtrip ────────────────────────────────────────────────
ok("correct password verifies", verify_password("correct horse battery staple", h) is True)
ok("wrong password rejected", verify_password("Tr0ub4dor&3", h) is False)
ok("empty password rejected", verify_password("", h) is False)

# ── verify_password defensive cases ──────────────────────────────────────────
ok("None stored hash rejected", verify_password("anything", None) is False)
ok("empty stored hash rejected", verify_password("anything", "") is False)
ok("malformed stored hash rejected", verify_password("anything", "not-a-valid-hash") is False)
ok("wrong-arity stored hash rejected", verify_password("anything", "a$b$c") is False)

# ── salt is random: same password → different stored hashes, both verify ─────
h2 = hash_password("correct horse battery staple")
ok("same password ⇒ different hash (random salt)", h != h2)
ok("both independent hashes verify", verify_password("correct horse battery staple", h2) is True)

# ── _issue_token (JWT) ───────────────────────────────────────────────────────
uid = uuid.uuid4()
new_user = User(id=uid, email="brand.new@narrative.dev", city=None)
tok = _issue_token(new_user)
ok("token payload has access_token", "access_token" in tok)
ok("new user flagged is_new_user (no city)", tok["is_new_user"] is True)

decoded = jwt.decode(tok["access_token"], settings.secret_key, algorithms=["HS256"])
ok("JWT sub == user id", decoded["sub"] == str(uid))
ok("JWT carries email", decoded["email"] == "brand.new@narrative.dev")
exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
days_out = (exp - datetime.now(timezone.utc)).days
ok("JWT expires ~30 days out", 28 <= days_out <= 30)

existing_user = User(id=uuid.uuid4(), email="returning@narrative.dev", city="London")
ok("returning user (has city) not flagged new", _issue_token(existing_user)["is_new_user"] is False)

# ── tamper rejection: wrong signing key fails to decode ──────────────────────
try:
    jwt.decode(tok["access_token"], "wrong-secret", algorithms=["HS256"])
    ok("token rejects wrong signing key", False)
except Exception:
    ok("token rejects wrong signing key", True)

# ── verification-key invariant ───────────────────────────────────────────────
# dependencies.get_current_user MUST verify with secret_key — the same key
# _issue_token signs with. A different key (e.g. a set SUPABASE_SERVICE_KEY) must
# NOT verify our tokens; the old `supabase_service_key or secret_key` fallback
# silently broke every login whenever that key was configured.
ok("issued token verifies under secret_key (the verify key)",
   jwt.decode(tok["access_token"], settings.secret_key, algorithms=["HS256"])["sub"] == str(uid))
try:
    jwt.decode(tok["access_token"], "a-set-supabase-service-key", algorithms=["HS256"])
    ok("token does NOT verify under a different (supabase) key", False)
except Exception:
    ok("token does NOT verify under a different (supabase) key", True)

print(f"\nauth: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
