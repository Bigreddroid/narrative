"""Property tests for the local LLM provider abstraction + cost guard (no DB/network).
Run from repo root:  python -m backend.services.llm_test
"""

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.config import get_settings
from backend.services import cost_guard, llm

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


s = get_settings()  # lru_cached; llm/cost_guard captured this same instance


def _set(provider):
    s.llm_provider = provider


# ── active_provider is local-only (ollama/off); no paid path exists ───────────
_set("ollama")
ok("ollama stays ollama", llm.active_provider() == "ollama")

_set("off")
ok("off stays off", llm.active_provider() == "off")
ok("available() False when provider off", llm.available() is False)

# ── 'off' provider raises BudgetExceeded (callers degrade) ───────────────────
try:
    llm.complete("sys", "user", 10)
    ok("complete raises when off", False)
except llm.BudgetExceeded:
    ok("complete raises when off", True)

# ── cost_guard: the local LLM is free, so a call is always allowed (no DB) ─────
_set("ollama")
ok("claude_allowed always True (local/free, db unused)",
   asyncio.run(cost_guard.claude_allowed(db=None)) is True)

# restore default
_set("ollama")

print(f"\nllm: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
