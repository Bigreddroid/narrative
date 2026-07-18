"""
Validate the calibration pipeline — reproducible, $0, no gated data.

WHAT THIS PROVES (and what it does NOT):
  ✓ PROVES the scoring + recalibration MATH in backend/consequence_engine/calibration.py
    is correct: on well-calibrated forecasts the pipeline reports ECE≈0 and a near-
    diagonal reliability curve; on deliberately miscalibrated (overconfident) forecasts,
    isotonic recalibration PROVABLY lowers Brier + ECE. This is a standard positive-control
    for a calibration estimator.
  ✗ Does NOT prove the consequence engine's own predictions are calibrated on real events —
    that requires real graded outcomes accruing in prediction_outcomes over time (see
    backtest_cpe.py Path A) or a real labeled dataset via backfill_prediction_outcomes.py.

Two modes:
  (default)        synthetic positive-control + recalibration-recovery (deterministic seed).
  --input FILE     score a REAL dataset: CSV/JSON of {prediction: 0-1, outcome: 0/1}. Drop in
                   a Metaculus export or Good-Judgment file (columns prediction,outcome) and
                   this reports its Brier / ECE / isotonic improvement on domain-real forecasts.

Usage:
    python scripts/validate_calibration.py
    python scripts/validate_calibration.py --input forecasts.csv --report out.txt
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.consequence_engine import calibration  # noqa: E402


def mean_brier(pairs, predict) -> float:
    return statistics.fmean(calibration.brier_score(predict(p), o) for p, o in pairs)


def synth_calibrated(n: int, seed: int = 42) -> list[tuple[float, float]]:
    """Well-calibrated stream: outcome ~ Bernoulli(p). A correct pipeline should
    report this as calibrated (ECE≈0)."""
    rng = random.Random(seed)
    pairs = []
    for _ in range(n):
        p = rng.random()
        pairs.append((p, 1.0 if rng.random() < p else 0.0))
    return pairs


def synth_overconfident(n: int, seed: int = 7) -> list[tuple[float, float]]:
    """Miscalibrated stream: stated prob is pushed toward the extremes vs the true
    rate, so the forecaster is systematically overconfident. Isotonic should pull it
    back and lower Brier."""
    rng = random.Random(seed)
    pairs = []
    for _ in range(n):
        true_p = rng.random()
        stated = true_p ** 0.45 if true_p >= 0.5 else 1 - (1 - true_p) ** 0.45  # push to extremes
        pairs.append((stated, 1.0 if rng.random() < true_p else 0.0))
    return pairs


def summarize(name: str, pairs: list[tuple[float, float]]) -> dict:
    n = len(pairs)
    brier = mean_brier(pairs, lambda p: p)
    ece = calibration.ece(pairs)
    model = calibration.fit_isotonic(pairs)
    recal = [(calibration.apply_isotonic(model, p), o) for p, o in pairs]
    brier_recal = mean_brier(recal, lambda p: p)
    ece_recal = calibration.ece(recal)
    return {
        "name": name, "n": n, "brier": brier, "ece": ece,
        "brier_recal": brier_recal, "ece_recal": ece_recal,
        "fitted": bool(model.get("xs")),
    }


def fmt(s: dict) -> str:
    tag = "recalibrated" if s["fitted"] else "identity (n<%d)" % calibration.MIN_CALIBRATION_POINTS
    return (
        f"{s['name']}  (n={s['n']})\n"
        f"  Brier            : {s['brier']:.4f}\n"
        f"  ECE              : {s['ece']:.4f}\n"
        f"  Brier (isotonic) : {s['brier_recal']:.4f}   [{tag}]\n"
        f"  ECE   (isotonic) : {s['ece_recal']:.4f}\n"
    )


def read_pairs(path: str) -> list[tuple[float, float]]:
    def rows():
        if path.lower().endswith(".json"):
            with open(path, encoding="utf-8") as f:
                yield from json.load(f)
        else:
            with open(path, newline="", encoding="utf-8") as f:
                yield from csv.DictReader(f)
    pairs = []
    for r in rows():
        p, o = float(r["prediction"]), float(r["outcome"])
        if 0.0 <= p <= 1.0 and o in (0.0, 1.0):
            pairs.append((p, o))
    return pairs


def run(pairs: list[tuple[float, float]] | None, report_path: str | None) -> int:
    lines = ["=== CALIBRATION PIPELINE VALIDATION ===\n"]

    if pairs is not None:
        s = summarize("REAL dataset (--input)", pairs)
        lines.append(fmt(s))
        lines.append("Note: this scores the SUPPLIED forecasts. It validates the pipeline on\n"
                     "domain-real data; it is not a claim about the consequence engine's own\n"
                     "predictions unless those forecasts ARE the engine's.\n")
        ok = True
    else:
        cal = summarize("positive control - CALIBRATED forecasts", synth_calibrated(2000))
        over = summarize("negative control - OVERCONFIDENT forecasts", synth_overconfident(2000))
        lines += [fmt(cal), fmt(over)]

        # Assertions that make this a PROOF, not just a printout.
        checks = [
            ("calibrated data reads as calibrated (ECE < 0.05)", cal["ece"] < 0.05),
            ("isotonic ~keeps calibrated Brier (no harm, <+0.005)", cal["brier_recal"] <= cal["brier"] + 0.005),
            ("overconfident data flagged (ECE > 0.05)", over["ece"] > 0.05),
            ("isotonic RECOVERS overconfident Brier (strictly lower)", over["brier_recal"] < over["brier"]),
            ("isotonic reduces overconfident ECE", over["ece_recal"] < over["ece"]),
        ]
        lines.append("--- PIPELINE CORRECTNESS CHECKS ---")
        ok = True
        for name, passed in checks:
            lines.append(f"  [{'PASS' if passed else 'FAIL'}] {name}")
            ok = ok and passed
        lines.append(
            f"\nVERDICT: pipeline {'VALIDATED - scoring + recalibration behave correctly' if ok else 'FAILED a correctness check'}.\n"
            "Scope: proves the calibration MATH. The engine's domain calibration still\n"
            "requires real graded outcomes (backtest_cpe.py Path A).\n"
        )

    out = "\n".join(lines)
    print(out)
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"[report written: {report_path}]")
    return 0 if ok else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate the calibration pipeline.")
    ap.add_argument("--input", help="real forecasts CSV/JSON (columns: prediction, outcome)")
    ap.add_argument("--report", help="also write the report to this path")
    args = ap.parse_args()
    pairs = read_pairs(args.input) if args.input else None
    sys.exit(run(pairs, args.report))


if __name__ == "__main__":
    main()
