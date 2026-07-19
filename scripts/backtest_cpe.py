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
from collections import Counter

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


async def load_pairs_pathb() -> list[tuple[float, float]]:
    """Path B ($0, no LLM, no 30-day wait): pair every stored prediction_score with a
    status-derived outcome label (resolved=1.0 / escalating=0.5 / stable=0.0) over all
    events that have reached a terminal status. Uses the whole local backlog, so N is
    large — but escalating→0.5 is a *soft* label, so watch the label distribution below:
    a set dominated by 0.5 is only weakly decisive, however many rows it has.
    """
    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        rows = await conn.fetch(
            """
            select m.prediction_score, e.current_status
            from event_consequence_maps m
            join narrative_events e on e.id = m.narrative_event_id
            where m.prediction_score is not null
            """
        )
    finally:
        await conn.close()

    pairs: list[tuple[float, float]] = []
    for score, status in rows:
        o = calibration.outcome_label(status)
        if o is None:
            continue  # still developing — not terminal, not scorable
        pairs.append((score / 100.0, float(o)))
    return pairs


def mean_brier(pairs, predict) -> float:
    return statistics.fmean(calibration.brier_score(predict(p, o), o) for p, o in pairs)


def decisive_only(pairs: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop soft 0.5 labels so the Brier-vs-base-rate comparison is on genuine
    {0,1} outcomes. Path B's escalating→0.5 dominates the set and makes every
    baseline collapse to the same number; on decisive labels the score has to
    actually separate resolved (1) from stable (0) to beat the base rate.
    """
    return [(p, o) for p, o in pairs if o in (0.0, 1.0)]


def report(pairs: list[tuple[float, float]]) -> None:
    n = len(pairs)
    print(f"\n=== CPE BACKTEST (Phase 0) — n={n} outcomes ===\n")
    if n == 0:
        print("No scorable outcomes. The algorithm is UNVALIDATED — nothing to grade.")
        return

    base_rate = statistics.fmean(o for _, o in pairs)
    fails = sum(1 for _, o in pairs if o == 0.0)
    dist = dict(sorted(Counter(round(o, 3) for _, o in pairs).items()))
    decisive = sum(v for k, v in dist.items() if k in (0.0, 1.0))
    print(f"label distribution (o→n)     : {dist}")
    print(f"decisive labels (o∈{{0,1}})    : {decisive} of {n}   "
          f"({'DEGENERATE — mostly soft 0.5' if decisive < n * 0.3 else 'ok'})")

    model_brier = mean_brier(pairs, lambda p, o: p)
    base_brier = mean_brier(pairs, lambda p, o: base_rate)
    coin_brier = mean_brier(pairs, lambda p, o: 0.5)
    model_ll = statistics.fmean(calibration.log_loss(p, o) for p, o in pairs)
    ece = calibration.ece(pairs)

    bss = calibration.brier_skill_score(pairs, reference_prob=base_rate)
    decomp = calibration.murphy_decomposition(pairs)

    print(f"outcome base rate (mean o)   : {base_rate:.3f}   ({fails} of {n} failed)")
    print(f"model  Brier (lower=better)  : {model_brier:.4f}")
    print(f"  vs always-base-rate Brier  : {base_brier:.4f}")
    print(f"  vs always-0.5 (coin) Brier : {coin_brier:.4f}")
    print(f"model  log-loss              : {model_ll:.4f}")
    print(f"model  ECE (calibration gap) : {ece:.4f}")
    # Brier Skill Score: the forecast-verification standard. >0 = genuine skill
    # over climatology (base rate); 0 = no better; <0 = worse. Quotable one number.
    bss_str = f"{bss:+.4f}" if bss is not None else "n/a (reference is degenerate)"
    print(f"model  Brier Skill Score     : {bss_str}   (>0 = skill over base rate)")
    # Murphy (1973): Brier = Reliability - Resolution + Uncertainty.
    print(
        f"Murphy decomp (rel-res+unc)  : {decomp['reliability']:.4f} - "
        f"{decomp['resolution']:.4f} + {decomp['uncertainty']:.4f} = {decomp['brier']:.4f}"
    )

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


def _print_pipeline_validation_banner() -> None:
    """Offline headline: the calibration-pipeline validation SCORE (no DB/network).

    Separate from and ABOVE the engine's own skill gate below, so the two are never
    conflated: this proves the scoring MATH is correct; PATH A proves (once n>=20)
    whether the engine's OWN predictions have skill."""
    try:
        from scripts.benchmark_score import synthetic_proof
        syn = synthetic_proof()
        p, t = syn["passed"], syn["total"]
        print(f"Pipeline validation: {p}/{t} controls PASS "
              f"(see scripts/benchmark_score.py for the full benchmark + real-data Brier).")
    except Exception as exc:  # never let the headline block the backtest
        print(f"Pipeline validation: unavailable ({exc}).")


async def main() -> None:
    print("################  PIPELINE VALIDATION (scoring math, $0, no data gate)  ################")
    _print_pipeline_validation_banner()
    print("\n################  PATH A — real graded outcomes (prediction_outcomes)  ################")
    report(await load_pairs())
    pathb = await load_pairs_pathb()
    print("\n\n################  PATH B — status-derived labels ($0, whole backlog)  ################")
    report(pathb)
    print("\n\n################  PATH B (DECISIVE) — 0.5 soft labels dropped, {0,1} only  ################")
    report(decisive_only(pathb))


if __name__ == "__main__":
    asyncio.run(main())
