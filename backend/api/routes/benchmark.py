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
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from backend.api.dependencies import DbDep
from backend.consequence_engine import calibration
from backend.models.benchmark_ledger import BenchmarkManifest, LedgerEntry
from backend.models.benchmark_runs import BenchmarkRun
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


async def _latest_run(db: DbDep) -> BenchmarkRun | None:
    """Latest cached benchmark_runs row (Phase 3), or None.

    Best-effort like _engine_accrual: a DB hiccup (or a fresh DB / CI with no
    Postgres, or the worker not having run yet) must not take down the public
    scoreboard, so we fall back to request-time compute rather than 500.
    """
    try:
        row = (await db.execute(
            select(BenchmarkRun).order_by(BenchmarkRun.run_at.desc()).limit(1)
        )).scalars().first()
        return row
    except Exception as exc:
        log.warning("benchmark: latest-run read failed (%s)", exc)
        try:
            await db.rollback()
        except Exception:
            pass
        return None


@router.get("/score")
async def get_benchmark_score(db: DbDep) -> dict:
    """The consolidated public scoreboard payload.

    Serves the latest cached benchmark_runs row (refreshed by benchmark_worker at
    benchmark_interval_days) with zero request-time compute or network. Until the
    first worker row exists (fresh DB / CI), it falls back to request-time proofs
    so the endpoint always returns the same shape. Either way it reuses
    benchmark_score.as_dict verbatim so the API can never drift from the CLI/CI
    numbers, and adds the reference bars, citations, and live engine-accrual meter.
    """
    run = await _latest_run(db)
    if run is not None and run.payload:
        payload = dict(run.payload)  # cached as_dict shape (synthetic/autocast/engine_gated)
        payload["cached_at"] = run.run_at.isoformat() if run.run_at else None
        payload["ledger_root_hash"] = run.ledger_root_hash
    else:
        # No cached row yet: compute now (never downloads in-request - guardrail #4).
        syn = _synthetic()
        auto = _autocast_no_network()
        payload = bs.as_dict(syn, auto)  # {synthetic, autocast, engine_gated}
        payload["cached_at"] = None
    payload["engine_accrual"] = await _engine_accrual(db)
    payload["reference_bars"] = REFERENCE_BARS
    payload["citations"] = CITATIONS
    payload["layers"] = LAYERS
    syn_block = payload.get("synthetic", {})
    payload["headline"] = (
        f"Calibration pipeline VALIDATED - {syn_block.get('passed')}/{syn_block.get('total')} "
        "synthetic controls; engine domain skill (BSS on its own predictions) accruing toward n>=20."
    )
    return payload


# --------------------------------------------------------------------------
# Phase 2: the public, tamper-evident forward prediction ledger.
#
# These serve PERSISTED rows only (written by scripts/publish_ledger.py +
# graded by outcome_worker) - no request-time compute, no network. Engine
# skill stays gated at n>=20; below the gate the endpoint returns
# status:"withheld" and NO Brier/BSS number.
# --------------------------------------------------------------------------

LEDGER_MAX_LIMIT = 500


def _parse_since(value: str | None) -> datetime | None:
    """Best-effort ISO-8601 parse for the ?since= filter (returns None on junk)."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _entry_dict(e: LedgerEntry) -> dict:
    """One ledger entry, public shape. Pre-resolution rows carry null outcomes."""
    return {
        "consequence_map_id": str(e.consequence_map_id),
        "question_text": e.question_text,
        "prediction_score": e.prediction_score,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "content_hash": e.content_hash,
        "manifest_date": e.manifest_date.isoformat() if e.manifest_date else None,
        "resolved": e.resolved_at is not None,
        "outcome": e.outcome,
        "observed_probability": e.observed_probability,
        "brier_score": e.brier_score,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
    }


@router.get("/ledger")
async def get_ledger(
    db: DbDep,
    since: str | None = Query(None, description="ISO-8601; only forecasts created at/after this time"),
    limit: int = Query(100, ge=1, le=LEDGER_MAX_LIMIT),
) -> dict:
    """Published forecasts + their content hashes (pre- and post-resolution).

    This is the auditable record: every forecast was hashed and committed BEFORE
    its outcome was known (verify against /ledger/manifest/{date}). Best-effort DB
    read - degrades to an empty list rather than a 500 if the DB is unreachable.
    """
    since_dt = _parse_since(since)
    entries: list[dict] = []
    try:
        stmt = select(LedgerEntry).order_by(LedgerEntry.created_at.desc()).limit(limit)
        if since_dt is not None:
            stmt = stmt.where(LedgerEntry.created_at >= since_dt)
        rows = (await db.execute(stmt)).scalars().all()
        entries = [_entry_dict(e) for e in rows]
    except Exception as exc:
        log.warning("benchmark: ledger read failed (%s)", exc)
        try:
            await db.rollback()
        except Exception:
            pass
    return {
        "count": len(entries),
        "since": since_dt.isoformat() if since_dt else None,
        "entries": entries,
        "note": (
            "Each entry's content_hash = sha256(question|score|created_at), committed "
            "before the outcome was known. Verify a day's set against its manifest root."
        ),
    }


@router.get("/ledger/manifest/{manifest_date}")
async def get_manifest(db: DbDep, manifest_date: str) -> dict:
    """The daily manifest root - the audit anchor a third party recomputes.

    Returns the stored root_hash + entry_count for the date plus that day's sorted
    content hashes, so anyone can recompute sha256(sorted hashes joined) and match
    it against docs/benchmark/manifest-<date>.txt committed to git.
    """
    day = _parse_since(manifest_date) or _parse_since(manifest_date + "T00:00:00")
    if day is None:
        return {"manifest_date": manifest_date, "found": False,
                "error": "unparseable date (want YYYY-MM-DD)"}
    d = day.date()
    try:
        manifest = (await db.execute(
            select(BenchmarkManifest).where(BenchmarkManifest.manifest_date == d)
        )).scalar_one_or_none()
        if manifest is None:
            return {"manifest_date": d.isoformat(), "found": False}
        hashes = [
            h for (h,) in (await db.execute(
                select(LedgerEntry.content_hash).where(LedgerEntry.manifest_date == d)
            )).all()
        ]
        return {
            "manifest_date": d.isoformat(),
            "found": True,
            "root_hash": manifest.root_hash,
            "entry_count": manifest.entry_count,
            "content_hashes": sorted(hashes),
            "note": "root_hash = sha256 of the sorted content_hashes concatenated.",
        }
    except Exception as exc:
        log.warning("benchmark: manifest read failed (%s)", exc)
        try:
            await db.rollback()
        except Exception:
            pass
        return {"manifest_date": d.isoformat(), "found": False, "error": "db_unavailable"}


@router.get("/engine-skill")
async def get_engine_skill(db: DbDep) -> dict:
    """Engine Brier Skill Score over RESOLVED ledger forecasts - GATED at n>=20.

    The clean, forward-looking skill claim: forecasts hashed before resolution,
    graded later. Below the gate we return status:"withheld" and NO number - the
    same refusal scripts/backtest_cpe.py holds. Never fabricates.
    """
    required = calibration.MIN_CALIBRATION_POINTS
    pairs: list[tuple[float, float]] = []
    try:
        rows = (await db.execute(
            select(LedgerEntry.prediction_score, LedgerEntry.observed_probability)
            .where(LedgerEntry.resolved_at.isnot(None))
            .where(LedgerEntry.observed_probability.isnot(None))
        )).all()
        pairs = [(s / 100.0, float(o)) for s, o in rows]
    except Exception as exc:
        log.warning("benchmark: engine-skill read failed (%s)", exc)
        try:
            await db.rollback()
        except Exception:
            pass

    n = len(pairs)
    if n < required:
        return {
            "status": "withheld",
            "resolved_n": n,
            "required": required,
            "note": (
                "Engine Brier Skill Score is withheld until n>=20 resolved forecasts. "
                "Any number below the gate is anecdote, not skill."
            ),
        }
    bss = calibration.brier_skill_score(pairs)  # None if the baseline is degenerate
    return {
        "status": "ready",
        "resolved_n": n,
        "required": required,
        "brier": round(sum(calibration.brier_score(p, o) for p, o in pairs) / n, 4),
        "brier_skill_score": round(bss, 4) if bss is not None else None,
        "note": (
            "Brier Skill Score over the engine's own forward forecasts, each hashed "
            "and committed before its outcome was known. Leak-proof by construction."
        ),
    }
