"""Property tests for the LLM provider abstraction + cost guard (no DB/network).
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


def _set(paid, provider):
    s.paid_apis_enabled = paid
    s.llm_provider = provider


# ── active_provider downgrade: paid stays off unless the master switch is on ──
_set(False, "anthropic")
ok("anthropic downgrades to ollama when paid disabled", llm.active_provider() == "ollama")
ok("is_paid False when paid disabled", llm.is_paid() is False)

_set(True, "anthropic")
ok("anthropic honoured when paid enabled", llm.active_provider() == "anthropic")
ok("is_paid True when paid enabled + anthropic", llm.is_paid() is True)

_set(False, "ollama")
ok("ollama stays ollama", llm.active_provider() == "ollama")

_set(True, "off")
ok("off stays off", llm.active_provider() == "off")
ok("available() False when provider off", llm.available() is False)

# ── 'off' provider raises BudgetExceeded (callers degrade) ───────────────────
_set(True, "off")
try:
    llm.complete("sys", "user", 10)
    ok("complete raises when off", False)
except llm.BudgetExceeded:
    ok("complete raises when off", True)

# ── anthropic cost estimate: $3/MTok in, $15/MTok out ────────────────────────
ok("estimate 1M in = $3", abs(llm.estimate_anthropic_cost(1_000_000, 0) - 3.0) < 1e-9)
ok("estimate 1M out = $15", abs(llm.estimate_anthropic_cost(0, 1_000_000) - 15.0) < 1e-9)

# ── cost_guard: free/local provider is always allowed (no DB touched) ─────────
_set(False, "ollama")
ok("claude_allowed True for free provider (db unused)",
   asyncio.run(cost_guard.claude_allowed(db=None)) is True)

_set(True, "anthropic")
ok("is_paid True ⇒ guard would consult DB", llm.is_paid() is True)

# restore defaults
_set(False, "ollama")

print(f"\nllm: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
