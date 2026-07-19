"""Asserts the Phase-3 benchmark worker's pure logic + honesty gate.
Run from repo root:  python -m backend.workers.benchmark_worker_test

Hermetic: no network, no DB, no LLM. The real Autocast download and the ledger
publish / row persistence are exercised by the live verification recipe, not
here - this test locks the contracts that must never regress:
  - _compute_proofs marks status "ok" only for a REAL Autocast number, "error"
    on selftest fallback (never fabricates a real number);
  - _engine_skill withholds the BSS (None) below the n>=20 gate and only emits a
    number at/above it - same refusal as the /engine-skill endpoint;
  - the cached flat columns are read straight from benchmark_score.as_dict, so
    the cache cannot drift from the CLI shape.
"""

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.consequence_engine import calibration
from backend.workers import benchmark_worker as bw
from scripts import benchmark_score as bs

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


def _is_ascii(obj) -> bool:
    if isinstance(obj, str):
        return obj.isascii()
    if isinstance(obj, dict):
        return all(_is_ascii(k) and _is_ascii(v) for k, v in obj.items())
    if isinstance(obj, list):
        return all(_is_ascii(x) for x in obj)
    return True


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDB:
    """Minimal async DB stub: returns preset ledger rows, or raises to exercise
    the best-effort rollback path."""
    def __init__(self, rows=None, raise_on_execute=False):
        self._rows = rows or []
        self._raise = raise_on_execute
        self.rolled_back = False

    async def execute(self, _query):
        if self._raise:
            raise RuntimeError("db down")
        return _FakeResult(self._rows)

    async def rollback(self):
        self.rolled_back = True


# --- _compute_proofs status labeling (stub autocast so there is no network) ---
_syn_stub = bs.synthetic_proof(200)  # small, pure, deterministic
_orig_autocast = bs.autocast_proof
_orig_synth = bs.synthetic_proof
try:
    bs.synthetic_proof = lambda *a, **k: _syn_stub
    bs.autocast_proof = lambda *a, **k: {"source": "real", "n": 100, "model_brier": 0.0948, "bss": 0.55}
    syn, auto, status = bw._compute_proofs()
    ok("real autocast -> status ok", status == "ok" and auto["source"] == "real")

    bs.autocast_proof = lambda *a, **k: {"source": "selftest", "n": 4, "model_brier": 0.0575, "bss": 0.5}
    syn, auto, status = bw._compute_proofs()
    ok("selftest fallback -> status error", status == "error" and auto["source"] == "selftest")

    # A raising autocast_proof(offline=False) must degrade, not crash.
    def _raising(*a, **k):
        if not k.get("offline"):
            raise RuntimeError("network down")
        return {"source": "selftest", "n": 4, "model_brier": 0.0575, "bss": 0.5}
    bs.autocast_proof = _raising
    syn, auto, status = bw._compute_proofs()
    ok("raising autocast degrades to selftest/error", status == "error" and auto["source"] == "selftest")
finally:
    bs.autocast_proof = _orig_autocast
    bs.synthetic_proof = _orig_synth


# --- engine-skill gate (the load-bearing honesty contract) ---
required = calibration.MIN_CALIBRATION_POINTS
ok("gate is n>=20", required == 20)

# Below the gate: BSS withheld (None), gate not met.
below_rows = [(70, 1.0), (30, 0.0), (60, 1.0)]  # n=3 < 20
n, bss, gate = asyncio.run(bw._engine_skill(_FakeDB(below_rows)))
ok("below gate: n reported", n == 3)
ok("below gate: BSS withheld (None)", bss is None)
ok("below gate: gate_met False", gate is False)

# At/above the gate: gate met; BSS is a float or None (degenerate baseline), never junk.
above_rows = [(70 if i % 2 else 30, 1.0 if i % 2 else 0.0) for i in range(25)]  # n=25 >= 20
n, bss, gate = asyncio.run(bw._engine_skill(_FakeDB(above_rows)))
ok("at gate: n reported", n == 25)
ok("at gate: gate_met True", gate is True)
ok("at gate: BSS is float or None", bss is None or isinstance(bss, float))

# DB failure: degrades to (0, None, False) and rolls back - never 500s the run.
fake = _FakeDB(raise_on_execute=True)
n, bss, gate = asyncio.run(bw._engine_skill(fake))
ok("db failure -> withheld", n == 0 and bss is None and gate is False)
ok("db failure -> rolled back", fake.rolled_back is True)


# --- cached flat columns are read straight from as_dict (no drift) ---
auto = {"source": "real", "n": 100, "model_brier": 0.0948, "base_brier": 0.2,
        "coin_brier": 0.25, "log_loss": 0.3, "ece": 0.05, "bss": 0.55, "beats_base_rate": True}
payload = bs.as_dict(_syn_stub, auto)
ab = payload["autocast"]
ok("as_dict autocast carries source", ab["source"] == "real")
ok("as_dict autocast carries model_brier", ab["model_brier"] == 0.0948)
ok("as_dict autocast carries bss", ab["bss"] == 0.55)
ok("as_dict engine_gated present", payload["engine_gated"]["requires_n"] == required)
ok("as_dict payload pure ASCII", _is_ascii(payload))

print(f"\nbenchmark_worker: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
