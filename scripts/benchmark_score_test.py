"""Deterministic proof of the validation-benchmark aggregator (seeded, no network).
Run:  python -m scripts.benchmark_score_test
"""
from scripts.benchmark_score import (
    _SELFTEST_PAIRS, as_dict, autocast_proof, render, synthetic_proof,
)
from backend.consequence_engine import calibration

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}")


# ── Proof A: synthetic controls ────────────────────────────────────────────────
syn = synthetic_proof()
ok("synthetic controls: 5/5 passed", syn["passed"] == 5 and syn["total"] == 5)
ok("positive control reads calibrated (ECE < 0.05)", syn["cal"]["ece"] < 0.05)
ok("negative control flagged (ECE > 0.05)", syn["over"]["ece"] > 0.05)
ok("isotonic strictly recovers overconfident Brier", syn["over"]["brier_recal"] < syn["over"]["brier"])

# Determinism: re-run must match to < 1e-12 (the "locked" claim on the deck).
again = synthetic_proof()
ok("synthetic run is reproducible (< 1e-12)",
   abs(again["over"]["brier"] - syn["over"]["brier"]) < 1e-12
   and again["passed"] == syn["passed"])

# ── Proof B: Autocast selftest fixture (offline path) ──────────────────────────
auto = autocast_proof(offline=True)
ok("autocast falls back to selftest when offline", auto["source"] == "selftest")
ok("selftest fixture Brier == 0.0575", abs(auto["model_brier"] - 0.0575) < 1e-9)
ok("selftest n == 4", auto["n"] == 4)

# BSS known-answer on the fixture: 1 - model/base, computed independently.
base = sum(o for _, o in _SELFTEST_PAIRS) / len(_SELFTEST_PAIRS)  # 0.5
base_brier = sum(calibration.brier_score(base, o) for _, o in _SELFTEST_PAIRS) / len(_SELFTEST_PAIRS)
expected_bss = 1.0 - (0.0575 / base_brier)
ok("selftest BSS matches 1 - model/base", abs(auto["bss"] - expected_bss) < 1e-9)
ok("crowd BEATS base-rate on fixture (0.0575 < 0.25)", auto["beats_base_rate"] is True)

# ── Headline render: must show the score AND the engine-gated scope ────────────
panel = render(syn, auto)
ok("headline shows 5/5", "5/5 synthetic controls" in panel)
ok("headline keeps engine-accuracy gated on n>=20", "gated on n>=20" in panel)
ok("headline labels Autocast as CROWD not engine skill", "NOT the engine's own skill" in panel)
ok("offline panel labels the selftest fallback", "selftest fixture" in panel)

# ── Machine-readable form for docs/artifact ────────────────────────────────────
d = as_dict(syn, auto)
ok("as_dict carries synthetic pass count", d["synthetic"]["passed"] == 5)
ok("as_dict keeps engine gate metadata", d["engine_gated"]["requires_n"] == 20)

print(f"\nbenchmark_score: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
