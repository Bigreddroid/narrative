"""
Benchmark API - the public, citable calibration scoreboard.

Phase 0 of the benchmark program: expose the scores we can ALREADY prove, with
the honesty boundaries the rest of the codebase enforces, so the numbers are
defensible to a judge / investor / journalist and re-runnable by anyone.

  GET /api/v1/benchmark/score  → the three honesty-separated layers:
      (1) pipeline correctness  - synthetic 5/5 controls (proven, deterministic)
      (2) external crowd bar     - Autocast Brier (OTHER forecasters, not us)
      (3) our engine             - Brier Skill Score, GATED on n>=20 graded
                                   outcomes; a live n/20 accrual meter, never a
                                   premature number.

Public, no auth: this is reference/proof data, not user data (mirrors
backend/api/routes/meta.py). It NEVER triggers a network download in-request and
NEVER emits an engine-skill number below the n>=20 gate - the same guardrails
that scripts/backtest_cpe.py and scripts/benchmark_score.py already hold.
"""
import logging
import os

from fastapi import APIRouter
from sqlalchemy import func, select

from backend.api.dependencies import DbDep
from backend.consequence_engine import calibration
from backend.models.prediction_outcome import PredictionOutcome
from scripts import benchmark_score as bs

router = APIRouter(prefix="/benchmark", tags=["benchmark"])
log = logging.getLogger(__name__)

# Field reference points (docs/CALIBRATION.md §3c) - so "good" is honest, not
# near-zero. Lower Brier is better; 0.25 is a coin flip.
REFERENCE_BARS = [
    {"label": "Coin flip", "brier": 0.25, "kind": "baseline",
     "note": "no skill - the honest floor"},
    {"label": "Superforecasters", "brier_low": 0.15, "brier_high": 0.20, "kind": "reference",
     "note": "Tetlock / Good Judgment elite humans on hard geopolitical questions"},
    {"label": "Autocast crowd", "brier": 0.0948, "bss": 0.547, "kind": "crowd",
     "note": "Metaculus / GJOpen / CSET crowds (Zou et al., 2022) - OTHER forecasters, not our engine"},
]

# Methodology citations (docs/CALIBRATION.md §3d).
CITATIONS = [
    "Brier, G.W. (1950). Verification of forecasts expressed in terms of probability. Monthly Weather Review.",
    "Murphy, A.H. (1973). A new vector partition of the probability score. Journal of Applied Meteorology.",
    "Gneiting, T. & Raftery, A.E. (2007). Strictly proper scoring rules, prediction, and estimation. JASA.",
    "Barnston, A.G. (1992) / WMO forecast-verification practice - Brier Skill Score vs climatology.",
    "Ayer, M. et al. (1955); Zadrozny & Elkan (2002) - isotonic regression / PAVA for probability calibration.",
    "Zou, A. et al. (2022). Forecasting Future World Events with Neural Networks (Autocast). NeurIPS.",
]

# The plain-language description of each honesty layer the scoreboard renders.
LAYERS = [
    {"id": "pipeline", "title": "Scoring pipeline is correct",
     "claim": "Our Brier / ECE / isotonic code detects miscalibration and provably corrects it.",
     "status": "proven"},
    {"id": "crowd", "title": "External crowd baseline (Autocast)",
     "claim": "The same math scores real crowd forecasts - an independent sanity check, NOT our engine's skill.",
     "status": "proven"},
    {"id": "engine", "title": "Our engine's own forecast skill",
     "claim": "Brier Skill Score on our live predictions, graded against real outcomes. Gated until n>=20 - no premature number.",
     "status": "accruing"},
]

# Compute the deterministic synthetic proof once (seeded, pure) and cache it -
# it can never drift, so there is no reason to recompute it per request.
_SYNTHETIC_CACHE: dict | None = None


def _synthetic() -> dict:
    global _SYNTHETIC_CACHE
    if _SYNTHETIC_CACHE is None:
        _SYNTHETIC_CACHE = bs.synthetic_proof()
    return _SYNTHETIC_CACHE


def _autocast_no_network() -> dict:
    """Autocast proof WITHOUT a request-time download (guardrail #4).

    Uses a previously-cached Autocast file if one exists on disk (populated by a
    prior CLI/worker run); otherwise falls back to the labeled offline selftest
    fixture. The Phase-3 benchmark worker refreshes the real cached number.
    """
    cache = bs._cache_path()
    if os.path.exists(cache) and os.path.getsize(cache) > 0:
        try:
            return bs.autocast_proof(autocast_file=cache)
        except Exception as exc:  # corrupt cache - degrade honestly, never fabricate
            log.warning("benchmark: cached Autocast unreadable (%s); using offline fixture", exc)
    return bs.autocast_proof(offline=True)


async def _engine_accrual(db: DbDep) -> dict:
    """Live n/20 accrual meter for the engine-skill gate.

    Counts genuinely graded outcomes (evaluated_at IS NOT NULL). Best-effort: a
    DB hiccup must not take down the public scoreboard, so it degrades to an
    'unknown' meter rather than a 500.
    """
    n = None
    try:
        result = await db.execute(
            select(func.count()).select_from(PredictionOutcome)
            .where(PredictionOutcome.evaluated_at.isnot(None))
        )
        n = int(result.scalar_one())
    except Exception as exc:
        # DB unreachable (e.g. CI without Postgres) must not 500 the public
        # scoreboard. Roll back so the session closes cleanly, then report the
        # meter as 'unknown' rather than fabricating a count.
        log.warning("benchmark: accrual count failed (%s)", exc)
        try:
            await db.rollback()
        except Exception:
            pass

    required = calibration.MIN_CALIBRATION_POINTS
    gate_met = n is not None and n >= required
    return {
        "graded_outcomes": n,
        "required": required,
        "gate_met": gate_met,
        # Below the gate we withhold ANY engine Brier/BSS - mirrors backtest_cpe.py.
        "status": "ready" if gate_met else "accruing",
        "note": (
            "Engine Brier Skill Score is withheld until n>=20 genuinely graded "
            "outcomes exist - any number below the gate is anecdote, not accuracy."
        ),
    }


@router.get("/score")
async def get_benchmark_score(db: DbDep) -> dict:
    """The consolidated public scoreboard payload.

    Reuses scripts/benchmark_score.py's proofs verbatim (as_dict) so the API can
    never drift from the CLI/CI numbers, and adds the reference bars, citations,
    and the live engine-accrual meter.
    """
    syn = _synthetic()
    auto = _autocast_no_network()
    payload = bs.as_dict(syn, auto)  # {synthetic, autocast, engine_gated}
    payload["engine_accrual"] = await _engine_accrual(db)
    payload["reference_bars"] = REFERENCE_BARS
    payload["citations"] = CITATIONS
    payload["layers"] = LAYERS
    payload["headline"] = (
        f"Calibration pipeline VALIDATED - {syn['passed']}/{syn['total']} synthetic controls; "
        "engine domain skill (BSS on its own predictions) accruing toward n>=20."
    )
    return payload
