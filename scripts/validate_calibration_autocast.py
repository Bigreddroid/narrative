"""
Calibration-PLUMBING validation on the Autocast dataset.

WHAT THIS IS: an independent check that our proper-scoring code
(backend/consequence_engine/calibration.py — brier_score, log_loss, ece,
reliability_curve, fit_isotonic) produces correct, sane numbers on a large,
known-well-calibrated dataset of real forecasts.

WHAT THIS IS **NOT**: it is NOT the CPE engine's Phase-0 skill gate. Autocast
contains *other* forecasters' predictions (Metaculus / Good Judgment Open / CSET
Foretell crowds), not our engine's. The Brier score printed here measures those
crowds' calibration, NOT whether The Narrative's consequence engine beats
base-rate. That gate can only be answered by grading the engine's OWN predictions
(prediction_outcomes over calendar time — see scripts/backtest_cpe.py). Keep the
two strictly separate so we never mislabel a crowd score as engine skill.

Dataset: Autocast (Zou et al., "Forecasting Future World Events with Neural
Networks", 2022). Download the questions file (no 200GB news corpus needed):

    git clone https://github.com/andyzoujm/autocast
    # → autocast/autocast_questions.json   (a few tens of MB)

Run:
    python scripts/validate_calibration_autocast.py --file path/to/autocast_questions.json
    python scripts/validate_calibration_autocast.py --selftest   # no download needed

Only true/false (binary) questions with a resolved yes/no answer are used, since a
Brier score needs a probability paired with a 0/1 outcome.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Make `backend` importable when run as a plain script from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.consequence_engine import calibration  # noqa: E402


def _crowd_prob_yes(crowd) -> float | None:
    """Final crowd probability of YES from an Autocast `crowd` forecast series.

    Autocast stores a time series of crowd forecasts; we take the LAST one (closest
    to resolution). A t/f forecast is either a scalar p(yes) or a [p(no), p(yes)]
    pair — tolerate both, and a bare list/number too."""
    if crowd is None:
        return None
    last = crowd[-1] if isinstance(crowd, list) and crowd else crowd
    if isinstance(last, dict):
        last = last.get("forecast", last.get("prob"))
    if isinstance(last, (list, tuple)):
        last = last[-1] if last else None  # [p_no, p_yes] → p_yes
    try:
        p = float(last)
    except (TypeError, ValueError):
        return None
    return p if 0.0 <= p <= 1.0 else None


def _answer_to_outcome(ans) -> float | None:
    """Autocast t/f resolution → 1.0 (yes) / 0.0 (no) / None (unresolved)."""
    if ans is None:
        return None
    s = str(ans).strip().lower()
    if s in ("yes", "y", "true", "1", "1.0"):
        return 1.0
    if s in ("no", "n", "false", "0", "0.0"):
        return 0.0
    return None


def extract_pairs(questions: list[dict]) -> list[tuple[float, float]]:
    """Autocast questions → [(p_yes, outcome)] over RESOLVED binary questions only.

    Pure/testable: no I/O. Skips non-binary questions, unresolved ones, and any whose
    crowd forecast is missing/out-of-range."""
    pairs: list[tuple[float, float]] = []
    for q in questions or []:
        if not isinstance(q, dict):
            continue
        qtype = str(q.get("qtype") or q.get("type") or "").lower()
        if qtype and qtype not in ("t/f", "tf", "binary", "true/false"):
            continue
        outcome = _answer_to_outcome(q.get("answer"))
        if outcome is None:
            continue
        p = _crowd_prob_yes(q.get("crowd"))
        if p is None:
            continue
        pairs.append((p, outcome))
    return pairs


def report(pairs: list[tuple[float, float]]) -> dict:
    """Run OUR calibration math over (p, outcome) pairs — the code under validation."""
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    base = sum(o for _, o in pairs) / n  # observed yes-rate = base-rate forecast
    model_brier = sum(calibration.brier_score(p, o) for p, o in pairs) / n
    base_brier = sum(calibration.brier_score(base, o) for _, o in pairs) / n
    coin_brier = sum(calibration.brier_score(0.5, o) for _, o in pairs) / n
    mean_logloss = sum(calibration.log_loss(p, o) for p, o in pairs) / n
    e = calibration.ece(pairs)
    iso = calibration.fit_isotonic(pairs)
    return {
        "n": n,
        "base_rate": base,
        "model_brier": model_brier,
        "base_brier": base_brier,
        "coin_brier": coin_brier,
        "log_loss": mean_logloss,
        "ece": e,
        "beats_base_rate": model_brier < base_brier,
        "isotonic_fitted": bool(iso.get("xs")),
        "reliability": calibration.reliability_curve(pairs),
    }


def _print_report(r: dict) -> None:
    print("=" * 72)
    print("AUTOCAST CALIBRATION-PLUMBING VALIDATION")
    print("Validates our Brier/ECE/isotonic code on Autocast crowd forecasts.")
    print("NOT the CPE engine's own skill (see scripts/backtest_cpe.py for that).")
    print("=" * 72)
    if r.get("n", 0) == 0:
        print("No usable resolved binary questions found — nothing to score.")
        return
    print(f"  resolved binary questions : {r['n']}")
    print(f"  base rate (yes)           : {r['base_rate']:.3f}")
    print(f"  crowd Brier               : {r['model_brier']:.4f}")
    print(f"  base-rate Brier           : {r['base_brier']:.4f}")
    print(f"  coin-flip Brier (0.5)     : {r['coin_brier']:.4f}")
    print(f"  mean log-loss             : {r['log_loss']:.4f}")
    print(f"  ECE                       : {r['ece']:.4f}")
    print(f"  isotonic map fitted       : {r['isotonic_fitted']} "
          f"(needs >= {calibration.MIN_CALIBRATION_POINTS} points)")
    verdict = "BEATS" if r["beats_base_rate"] else "does NOT beat"
    print(f"  --> crowd {verdict} the base-rate baseline "
          "(expected: a calibrated crowd beats base-rate; a sanity check on our math)")


# ── self-test: proves the plumbing on hand-computed values, no download needed ──
def _selftest() -> int:
    # Four pairs with a KNOWN Brier: errors 0.1^2,0.2^2,0.3^2,0.3^2 = .01+.04+.09+.09
    fixture = [(0.9, 1.0), (0.2, 0.0), (0.7, 1.0), (0.3, 0.0)]
    expected_brier = (0.01 + 0.04 + 0.09 + 0.09) / 4  # 0.0575
    got = sum(calibration.brier_score(p, o) for p, o in fixture) / len(fixture)
    assert abs(got - expected_brier) < 1e-9, f"brier mismatch: {got} != {expected_brier}"

    # Parser: one resolved t/f (kept), one unresolved (dropped), one numeric (dropped).
    questions = [
        {"qtype": "t/f", "answer": "yes", "crowd": [{"forecast": 0.8}]},
        {"qtype": "t/f", "answer": None, "crowd": [{"forecast": 0.5}]},
        {"qtype": "num", "answer": "42", "crowd": [{"forecast": 0.5}]},
        {"qtype": "t/f", "answer": "no", "crowd": [0.1, 0.3]},  # [p_no, p_yes]→0.3
    ]
    pairs = extract_pairs(questions)
    assert pairs == [(0.8, 1.0), (0.3, 0.0)], f"parser extracted: {pairs}"

    r = report(fixture)
    assert r["n"] == 4 and abs(r["model_brier"] - expected_brier) < 1e-9
    print("selftest: OK — calibration plumbing + Autocast parser verified")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", default=os.environ.get("AUTOCAST_QUESTIONS"),
                    help="path to autocast_questions.json")
    ap.add_argument("--selftest", action="store_true",
                    help="validate the math/parser on a built-in fixture (no download)")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if not args.file:
        ap.error("pass --file autocast_questions.json (or set AUTOCAST_QUESTIONS), "
                 "or use --selftest. Download: git clone https://github.com/andyzoujm/autocast")
    with open(args.file, encoding="utf-8") as fh:
        data = json.load(fh)
    questions = data if isinstance(data, list) else data.get("questions", data.get("data", []))
    _print_report(report(extract_pairs(questions)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
