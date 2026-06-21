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

print(f"\ncalibration: {passed} passed, {failed} failed (ECE {ece_raw:.3f} -> {ece_cal:.3f})")
raise SystemExit(1 if failed else 0)
