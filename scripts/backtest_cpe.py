"""
Phase 0 — CPE backtest. Answers one question honestly: does the prediction score
actually predict reality, and how well is it calibrated?

$0 / local. Reads the proprietary calibration set (prediction_outcomes) and scores
it with backend.consequence_engine.calibration (Brier / log-loss / ECE / reliability),
then compares the model against dumb baselines. If the model can't beat "always
predict the base rate", the score is not yet earning its keep — and we say so.

The observed outcome o is taken from observed_probability when present, else derived
from actual_outcome via the same {materialized:1, partial:0.5, failed:0} map the
outcome_worker uses — so historical rows written before the scoring columns existed
are still usable.

Run:  python scripts/backtest_cpe.py
Env:  DATABASE_URL (asyncpg URL, same as the app).
"""

import asyncio
import os
import statistics

import asyncpg

from backend.consequence_engine import calibration

_OUTCOME_TO_PROB = {"materialized": 1.0, "partial": 0.5, "failed": 0.0}


def _asyncpg_dsn() -> str:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://narrative:narrative123@127.0.0.1:5432/narrative",
    )
    # asyncpg wants a plain postgresql:// DSN, not the SQLAlchemy +asyncpg scheme,
    # and doesn't accept the ?ssl=disable query the app URL sometimes carries.
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url.split("?", 1)[0]


async def load_pairs() -> list[tuple[float, float]]:
    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        rows = await conn.fetch(
            """
            select original_prediction_score, observed_probability, actual_outcome
            from prediction_outcomes
            where original_prediction_score is not null
            """
        )
    finally:
        await conn.close()

    pairs: list[tuple[float, float]] = []
    for score, obs, outcome in rows:
        o = obs if obs is not None else _OUTCOME_TO_PROB.get((outcome or "").lower())
        if o is None:
            continue  # unresolved / unknown label — not scorable
        pairs.append((score / 100.0, float(o)))
    return pairs


def mean_brier(pairs, predict) -> float:
    return statistics.fmean(calibration.brier_score(predict(p, o), o) for p, o in pairs)


def report(pairs: list[tuple[float, float]]) -> None:
    n = len(pairs)
    print(f"\n=== CPE BACKTEST (Phase 0) — n={n} outcomes ===\n")
    if n == 0:
        print("No scorable outcomes. The algorithm is UNVALIDATED — nothing to grade.")
        return

    base_rate = statistics.fmean(o for _, o in pairs)
    fails = sum(1 for _, o in pairs if o == 0.0)

    model_brier = mean_brier(pairs, lambda p, o: p)
    base_brier = mean_brier(pairs, lambda p, o: base_rate)
    coin_brier = mean_brier(pairs, lambda p, o: 0.5)
    model_ll = statistics.fmean(calibration.log_loss(p, o) for p, o in pairs)
    ece = calibration.ece(pairs)

    print(f"outcome base rate (mean o)   : {base_rate:.3f}   ({fails} of {n} failed)")
    print(f"model  Brier (lower=better)  : {model_brier:.4f}")
    print(f"  vs always-base-rate Brier  : {base_brier:.4f}")
    print(f"  vs always-0.5 (coin) Brier : {coin_brier:.4f}")
    print(f"model  log-loss              : {model_ll:.4f}")
    print(f"model  ECE (calibration gap) : {ece:.4f}")

    print("\nreliability (predicted vs observed):")
    for b in calibration.reliability_curve(pairs):
        print(
            f"  [{b['lo']:.1f},{b['hi']:.1f})  n={b['count']:>2}  "
            f"pred~{b['mean_pred']:.2f}  obs~{b['obs_freq']:.2f}"
        )

    print("\n--- VERDICT ---")
    if n < calibration.MIN_CALIBRATION_POINTS:
        print(
            f"n={n} < {calibration.MIN_CALIBRATION_POINTS}: NOT ENOUGH DATA to validate "
            "or recalibrate. Any number above is anecdote, not accuracy."
        )
    if fails == 0:
        print(
            "Zero failed outcomes in the set: the grader has never seen the model be "
            "wrong, so 'accuracy' is untestable (a stopped clock scores well here)."
        )
    beats = model_brier < base_brier
    print(
        f"Model {'BEATS' if beats else 'does NOT beat'} the base-rate baseline "
        f"({model_brier:.4f} vs {base_brier:.4f}). "
        + ("Score adds signal." if beats else "Score is not yet earning its keep.")
    )


async def main() -> None:
    report(await load_pairs())


if __name__ == "__main__":
    asyncio.run(main())
