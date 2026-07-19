"""Property tests for the deep OODA reasoner's DEGRADE contract (no DB, no network).

The deep analyst (services/reasoner.py) is one of the five LLM surfaces the deploy
guarantee covers: with the provider off, unreachable, or the call budget spent, it
must degrade cleanly and NEVER raise (no 500). Its full loop needs a DB, but the
degrade contract lives in the cost-gated `_llm` helper and the `_orient` thread
parser, which forward `db` only to `cost_guard.llm_allowed` (that ignores db). So we
swap out llm.available / llm.complete and exercise them deterministically offline.

Run from repo root:  python -m backend.services.reasoner_test
"""

import asyncio
import sys
from types import SimpleNamespace

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.services import llm, reasoner as R

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


def run(coro):
    return asyncio.run(coro)


def _no_call(*a, **k):
    raise AssertionError("LLM must not be called on this path")


_real_available, _real_complete = llm.available, llm.complete
B = R._CallBudget

try:
    # ── budget cap: an exhausted budget returns None before any LLM call ──
    llm.available = lambda: True
    llm.complete = _no_call
    ok("_llm returns None when call budget is spent", run(R._llm(None, "s", "u", B(0), 100)) is None)

    # ── provider unavailable: the cost gate stops the chain, no LLM call, no raise ──
    llm.available = lambda: False
    ok("_llm returns None when provider unavailable", run(R._llm(None, "s", "u", B(6), 100)) is None)

    # ── provider up but the call errors: degrade to None, never propagate a 500 ──
    llm.available = lambda: True

    def _raise_budget(*a, **k):
        raise llm.BudgetExceeded("LLM provider is 'off'")

    llm.complete = _raise_budget
    ok("_llm degrades to None on BudgetExceeded (provider off)", run(R._llm(None, "s", "u", B(6), 100)) is None)

    def _raise_transport(*a, **k):
        raise RuntimeError("ollama connection refused")

    llm.complete = _raise_transport
    ok("_llm degrades to None on transport error", run(R._llm(None, "s", "u", B(6), 100)) is None)

    # ── happy path: returns the model text ──
    llm.complete = lambda **k: SimpleNamespace(text="hello", provider="ollama", cost_usd=0.0)
    ok("_llm returns text on success", run(R._llm(None, "s", "u", B(6), 100)) == "hello")

    # ── _orient parses threads from valid JSON and caps to MAX_THREADS ──
    many = '{"threads":[{"focus":"a","why":"x"},{"focus":"b","why":"y"},{"focus":"c"},{"focus":"d"}]}'
    llm.complete = lambda **k: SimpleNamespace(text=many, provider="ollama", cost_usd=0.0)
    threads = run(R._orient(None, "q", "ctx", [], B(6)))
    ok("_orient parses threads in order", [t["focus"] for t in threads[:2]] == ["a", "b"])
    ok("_orient caps at MAX_THREADS", len(threads) == R.MAX_THREADS)

    # ── _orient degrades to [] on unparseable output (no raise) ──
    llm.complete = lambda **k: SimpleNamespace(text="not json at all", provider="ollama", cost_usd=0.0)
    ok("_orient returns [] on unparseable output", run(R._orient(None, "q", "ctx", [], B(6))) == [])

    # ── _orient degrades to [] when the chain can't reach the LLM ──
    llm.available = lambda: False
    ok("_orient returns [] when provider unavailable", run(R._orient(None, "q", "ctx", [], B(6))) == [])
finally:
    llm.available, llm.complete = _real_available, _real_complete

print(f"\nreasoner: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
