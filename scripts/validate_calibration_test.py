"""Deterministic proof that the calibration pipeline is correct (seeded, no I/O).
Run:  python -m scripts.validate_calibration_test
"""
from scripts.validate_calibration import synth_calibrated, synth_overconfident, summarize

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}")


cal = summarize("calibrated", synth_calibrated(2000, seed=42))
over = summarize("overconfident", synth_overconfident(2000, seed=7))

# Positive control: calibrated data must read as calibrated.
ok("calibrated ECE < 0.05", cal["ece"] < 0.05)
ok("isotonic does not harm calibrated Brier", cal["brier_recal"] <= cal["brier"] + 0.005)

# Negative control: miscalibration is detected AND recalibration recovers it.
ok("overconfident ECE > 0.05", over["ece"] > 0.05)
ok("isotonic strictly lowers overconfident Brier", over["brier_recal"] < over["brier"])
ok("isotonic lowers overconfident ECE", over["ece_recal"] < over["ece"])

# Determinism: same seed ⇒ same numbers (so CI/proof is reproducible).
again = summarize("overconfident", synth_overconfident(2000, seed=7))
ok("seeded run is reproducible", abs(again["brier"] - over["brier"]) < 1e-12)

print(f"\nvalidate_calibration: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
