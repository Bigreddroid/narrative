"""
STEP 11 - CONTINUOUS BENCHMARK (every benchmark_interval_days).

Keeps the public /benchmark/score board live without any request-time compute or
network. Once per cadence this worker:

  1. Recomputes the synthetic controls (pure) and the REAL Autocast crowd Brier
     (online download, refreshing the on-disk /tmp cache as a side effect). On
     any acquisition failure it falls back to the labeled selftest fixture and
     marks the run status "error" - it never fabricates a real number.
  2. Auto-publishes the forward prediction ledger (reuses scripts.publish_ledger:
     hashes new confident forecasts, rolls the daily manifest root, and writes
     the git-committable docs/benchmark/manifest-<date>.txt anchor).
  3. Recomputes engine skill (Brier Skill Score) over RESOLVED ledger forecasts -
     GATED at n>=20; below the gate engine_bss stays NULL (same refusal the
     /engine-skill endpoint holds).
  4. Persists one benchmark_runs row (payload = benchmark_score.as_dict verbatim
     so the endpoint cannot drift) plus a PipelineMetric row.

Deliberately has NO no-LLM guard: none of these steps call the LLM (synthetic +
crowd Brier are data-only; ledger publish is pure hashing; engine skill reads
already-graded outcomes). So it runs identically on the local Docker stack and on
Railway - there is no honest-degradation gap for these layers.
"""

import asyncio
import logging
import time
import uuid

from sqlalchemy import select

from backend.config import get_settings
from backend.consequence_engine import calibration
from backend.database import AsyncSessionLocal
from backend.models.benchmark_ledger import LedgerEntry
from backend.models.benchmark_runs import BenchmarkRun
from backend.models.pipeline_metrics import PipelineMetric
from scripts import benchmark_score as bs
from scripts import publish_ledger

logger = logging.getLogger(__name__)
settings = get_settings()


def _compute_proofs() -> tuple[dict, dict, str]:
    """Synthetic (pure) + real Autocast proofs. Never fabricates a real number.

    Returns (syn, auto, status): status is "ok" when the real Autocast dataset
    was scored, "error" when we fell back to the labeled selftest fixture.
    """
    syn = bs.synthetic_proof()
    try:
        auto = bs.autocast_proof(offline=False)
    except Exception as exc:  # defensive: autocast_proof already self-guards, but be safe
        logger.warning("benchmark_worker: autocast proof failed (%s); using offline fixture", exc)
        auto = bs.autocast_proof(offline=True)
    # autocast_proof marks source="selftest" on any acquisition failure/offline.
    status = "ok" if auto.get("source") == "real" else "error"
    return syn, auto, status


async def _engine_skill(db) -> tuple[int, float | None, bool]:
    """(engine_n, engine_bss, gate_met) over RESOLVED ledger forecasts.

    Mirrors backend/api/routes/benchmark.py::get_engine_skill exactly so the
    cached number can never disagree with the live /engine-skill endpoint. Below
    the n>=20 gate the BSS is withheld (returned as None).
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
        logger.warning("benchmark_worker: engine-skill read failed (%s)", exc)
        try:
            await db.rollback()
        except Exception:
            pass

    n = len(pairs)
    if n < required:
        return n, None, False
    bss = calibration.brier_skill_score(pairs)  # None if the baseline is degenerate
    return n, (round(bss, 4) if bss is not None else None), True


async def run_benchmark_worker() -> dict:
    start = time.perf_counter()

    # Steps 1-3 are LLM-free. Autocast download + synthetic controls are CPU/data
    # only; ledger publish is pure hashing; engine skill reads graded outcomes.
    syn, auto, status = _compute_proofs()

    # Auto-publish the forward ledger (own asyncpg connection, idempotent).
    ledger_published = ledger_root = ledger_count = None
    try:
        res = await publish_ledger._run(limit=settings.benchmark_publish_limit, dry_run=False)
        ledger_published = res.get("new_entries")
        ledger_root = res.get("root_hash")
        ledger_count = res.get("entry_count")
    except Exception as exc:
        logger.error("benchmark_worker: ledger publish failed (%s)", exc)
        status = "error"

    async with AsyncSessionLocal() as db:
        engine_n, engine_bss, gate_met = await _engine_skill(db)

        payload = bs.as_dict(syn, auto)  # {synthetic, autocast, engine_gated}
        auto_block = payload["autocast"]

        db.add(BenchmarkRun(
            id=uuid.uuid4(),
            status=status,
            synthetic_passed=syn["passed"],
            synthetic_total=syn["total"],
            autocast_source=auto_block.get("source"),
            autocast_n=auto_block.get("n"),
            autocast_brier=auto_block.get("model_brier"),
            autocast_bss=auto_block.get("bss"),
            ledger_published=ledger_published,
            ledger_root_hash=ledger_root,
            ledger_entry_count=ledger_count,
            engine_n=engine_n,
            engine_bss=engine_bss,
            engine_gate_met=gate_met,
            payload=payload,
            duration_seconds=round(time.perf_counter() - start, 2),
        ))
        db.add(PipelineMetric(
            id=uuid.uuid4(),
            worker_name="benchmark_worker",
            errors=1 if status == "error" else 0,
            duration_seconds=round(time.perf_counter() - start, 2),
        ))
        await db.commit()

    summary = {
        "status": status,
        "autocast_source": auto_block.get("source"),
        "autocast_brier": auto_block.get("model_brier"),
        "ledger_published": ledger_published,
        "engine_n": engine_n,
        "engine_gate_met": gate_met,
    }
    logger.info(
        "Benchmark worker done: status=%s autocast=%s brier=%s published=%s engine_n=%d gate=%s",
        status, auto_block.get("source"), auto_block.get("model_brier"),
        ledger_published, engine_n, gate_met,
    )
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(run_benchmark_worker()))
