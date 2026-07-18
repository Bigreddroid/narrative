"""
Property test for calibration (pure, stdlib only). Run from repo root:
    python -m backend.consequence_engine.calibration_test
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.consequence_engine import calibration as C

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# proper scoring rules
ok("brier perfect = 0", C.brier_score(1.0, 1.0) == 0.0)
ok("brier worst = 1", C.brier_score(1.0, 0.0) == 1.0)
ok("log_loss perfect ~ 0", C.log_loss(1.0, 1.0) < 1e-6)
ok("log_loss finite at extremes", C.log_loss(0.0, 1.0) < 100 and C.log_loss(1.0, 0.0) < 100)

# ground-truth labels
ok("resolved => materialized", C.outcome_label("resolved") == 1.0)
ok("escalating => partial", C.outcome_label("escalating") == 0.5)
ok("stable => failed", C.outcome_label("stable") == 0.0)
ok("developing => pending", C.outcome_label("developing") is None)
ok("explicit impacts override status", C.outcome_label("stable", impacts_materialized=True) == 1.0)

# reliability curve
pairs = [(0.2, 0), (0.2, 1), (0.8, 1), (0.8, 1)]
curve = C.reliability_curve(pairs, n_bins=10)
ok("reliability bins counted", sum(b["count"] for b in curve) == len(pairs))

# ece: perfectly calibrated => ~0
perfect = [(0.0, 0)] * 10 + [(1.0, 1)] * 10
ok("ECE ~0 when perfectly calibrated", C.ece(perfect) < 1e-9)

# --- KEY DS PROPERTY: isotonic recalibration reduces ECE on a miscalibrated set ---
levels = [0.2, 0.4, 0.6, 0.8]
raw = []
for lv in levels:
    true_rate = lv * 0.6  # systematically overconfident model
    n_pos = round(25 * true_rate)
    raw += [(lv, 1.0)] * n_pos + [(lv, 0.0)] * (25 - n_pos)

model = C.fit_isotonic(raw)
calibrated = [(C.apply_isotonic(model, p), o) for p, o in raw]
ece_raw, ece_cal = C.ece(raw), C.ece(calibrated)
ok("recalibration lowers ECE", ece_cal < ece_raw)
ok("isotonic map is monotonic", all(model["ys"][i] <= model["ys"][i + 1] for i in range(len(model["ys"]) - 1)))
ok("calibrated probs within [0,1]", all(0 <= C.apply_isotonic(model, p) <= 1 for p in (0.0, 0.3, 0.5, 0.9, 1.0)))

# identity until enough data
ok("identity below min points", C.fit_isotonic([(0.5, 1.0)] * 5) == {"xs": [], "ys": []})
ok("identity map returns input", C.apply_isotonic({"xs": [], "ys": []}, 0.37) == 0.37)

# pattern-conditioned base rates
br = C.base_rates([
    {"pattern": "conflict", "outcome": 1.0}, {"pattern": "conflict", "outcome": 1.0}, {"pattern": "conflict", "outcome": 0.0},
    {"pattern": "economics", "outcome": 0.0}, {"pattern": "economics", "outcome": 0.0},
])
ok("base rate per pattern", abs(br["conflict"] - 0.667) < 0.01 and br["economics"] == 0.0)
ok("base_rates empty ⇒ empty", C.base_rates([]) == {})

# --- Brier Skill Score (forecast-verification standard) ---
ok("BSS = 0 when model equals base rate", abs(C.brier_skill_score([(0.5, 1.0), (0.5, 0.0)]) - 0.0) < 1e-12)
ok("BSS = 1 for a perfect model", abs(C.brier_skill_score([(1.0, 1.0), (0.0, 0.0)]) - 1.0) < 1e-12)
ok("BSS < 0 when worse than base rate", C.brier_skill_score([(0.9, 1.0), (0.9, 0.0)]) < 0.0)
ok("BSS honors explicit reference_prob", abs(C.brier_skill_score([(0.5, 1.0), (0.5, 0.0)], reference_prob=0.5) - 0.0) < 1e-12)
ok("BSS None on empty", C.brier_skill_score([]) is None)
ok("BSS None when reference is perfect (single-outcome set)", C.brier_skill_score([(0.3, 1.0), (0.7, 1.0)]) is None)

# --- Murphy decomposition: Brier = Reliability - Resolution + Uncertainty (exact for binary) ---
def _mean_brier(prs):
    return sum(C.brier_score(p, o) for p, o in prs) / len(prs)

# perfectly resolving & reliable: rel=0, res=unc=0.25, brier=0
d1 = C.murphy_decomposition([(0.0, 0.0)] * 5 + [(1.0, 1.0)] * 5)
ok("Murphy: reliability 0 when calibrated", abs(d1["reliability"]) < 1e-12)
ok("Murphy: resolution == uncertainty when perfectly resolving", abs(d1["resolution"] - d1["uncertainty"]) < 1e-12)
ok("Murphy: brier reconstruction == 0 here", abs(d1["brier"]) < 1e-12)

# miscalibrated single-group: forecast 0.8, outcomes 3x1 + 2x0 -> rel=0.04, res=0, unc=0.24, brier=0.28
mis = [(0.8, 1.0)] * 3 + [(0.8, 0.0)] * 2
d2 = C.murphy_decomposition(mis)
ok("Murphy: reliability known value", abs(d2["reliability"] - 0.04) < 1e-12)
ok("Murphy: resolution 0 for single group", abs(d2["resolution"]) < 1e-12)
ok("Murphy: uncertainty known value", abs(d2["uncertainty"] - 0.24) < 1e-12)
ok("Murphy: reconstruction == mean Brier (binary)", abs(d2["brier"] - _mean_brier(mis)) < 1e-12)

# reconstruction identity holds on an arbitrary binary set
arb = [(0.2, 0.0), (0.2, 1.0), (0.7, 1.0), (0.7, 1.0), (0.9, 0.0), (0.4, 1.0), (0.4, 0.0)]
d3 = C.murphy_decomposition(arb)
ok("Murphy: REL - RES + UNC == mean Brier on arbitrary binary set", abs(d3["brier"] - _mean_brier(arb)) < 1e-12)
ok("Murphy: empty set is all zeros", C.murphy_decomposition([]) == {"reliability": 0.0, "resolution": 0.0, "uncertainty": 0.0, "brier": 0.0})

print(f"\ncalibration: {passed} passed, {failed} failed (ECE {ece_raw:.3f} -> {ece_cal:.3f})")
raise SystemExit(1 if failed else 0)
