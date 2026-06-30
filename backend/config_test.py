"""Property tests for Settings (pure, no DB). Run from repo root:
    python -m backend.config_test

Guards the DATABASE_URL driver normalization: the app's async engine needs the
asyncpg driver, but managed hosts (Railway) inject a plain postgresql:// URL.
config.py must rewrite it so the app boots.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.config import Settings

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


def db(url: str) -> str:
    return Settings(database_url=url).database_url


ok("plain postgresql:// gets +asyncpg",
   db("postgresql://u:p@host:5432/db") == "postgresql+asyncpg://u:p@host:5432/db")
ok("postgres:// alias gets +asyncpg",
   db("postgres://u:p@host:5432/db") == "postgresql+asyncpg://u:p@host:5432/db")
ok("already +asyncpg is unchanged (idempotent)",
   db("postgresql+asyncpg://u:p@host:5432/db") == "postgresql+asyncpg://u:p@host:5432/db")
ok("query string is preserved",
   db("postgresql://u:p@host:5432/db?sslmode=require")
   == "postgresql+asyncpg://u:p@host:5432/db?sslmode=require")
ok("password with embedded scheme-like text is not double-rewritten",
   db("postgresql://u:postgresql@host/db") == "postgresql+asyncpg://u:postgresql@host/db")
ok("default URL already uses asyncpg",
   Settings().database_url.startswith("postgresql+asyncpg://"))

# ── production secret-key guard (fail closed) ────────────────────────────────────
# Pass secret_key explicitly so the assertions don't depend on a local .env (which
# may set a real SECRET_KEY and mask the default).
_DEF = "dev-secret-key-change-in-production"


def _raises(**kw) -> bool:
    try:
        Settings(**kw)
        return False
    except Exception:
        return True


ok("dev default secret is fine outside production",
   Settings(app_env="development", secret_key=_DEF).secret_key == _DEF)
ok("production + default secret → boot refused", _raises(app_env="production", secret_key=_DEF))
ok("production + empty secret → boot refused", _raises(app_env="production", secret_key=""))
ok("production + real secret → boots",
   Settings(app_env="production", secret_key="a" * 64).secret_key == "a" * 64)

print(f"\nconfig: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
