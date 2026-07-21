"""
EXTERNAL RESOLUTION WORKER — grade forward-mode external forecasts.

The companion to scripts/publish_external_forecasts.py. Those entries
(benchmark_ledger.source != 'engine') are forecasts the engine published on OPEN
outside questions; the SOURCE resolves them later. This worker re-queries the
source by external_ref and, when it reports a clean YES/NO, backfills the ledger
entry's resolution fields (outcome / observed_probability / brier_score /
resolved_at) — exactly mirroring how outcome_worker grades internal forecasts.

LLM-FREE (pure HTTP + arithmetic), so it is safe to run on any host. It only
touches rows that already exist locally: external forecasts are published on the
authoritative (local) stack, so on a host that never published any this worker
simply finds nothing to grade. It never writes the manifest (content_hash /
created_at are write-once), so it cannot fork the audit chain.

Honest by design: an ambiguous / partial / cancelled (MKT, N-A, CANCEL) or
still-open market resolves to None here and the entry is LEFT OPEN for a later
run. We never force a 0/1.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from backend.config import get_settings
from backend.consequence_engine import calibration
from backend.database import AsyncSessionLocal
from backend.models.benchmark_ledger import LedgerEntry
from backend.models.pipeline_metrics import PipelineMetric

# The pure source helpers live with the other external-dataset adapters.
from scripts import external_benchmark as eb

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_PER_RUN = 200  # bound HTTP fan-out per run


def _manifold_contract_id(external_ref: str) -> str | None:
    """'manifold:<contractId>' -> '<contractId>'. Unknown scheme -> None (skip)."""
    if not external_ref or not external_ref.startswith("manifold:"):
        return None
    cid = external_ref.split(":", 1)[1].strip()
    return cid or None


def _outcome_label(obs: float) -> str:
    """Realised 0/1 -> the ledger's outcome label (mirrors outcome_worker's vocab)."""
    return "materialized" if obs >= 0.5 else "failed"


async def _resolve_one(entry) -> float | None:
    """Re-query the source for one entry -> realised outcome 1.0/0.0, or None.

    None = not cleanly resolved yet (still open, ambiguous, or a source we don't
    poll) -> leave the entry open. Network errors also return None (retry later).
    """
    cid = _manifold_contract_id(entry.external_ref or "")
    if cid is None:
        return None
    try:
        market = await asyncio.to_thread(eb.manifold_market_by_id, cid)
    except Exception as exc:
        logger.warning("external resolution: fetch failed for %s (%s)", entry.external_ref, exc)
        return None
    return eb.resolution_from_manifold_market(market)


async def run_external_resolution_worker() -> dict:
    start = time.perf_counter()
    resolved = still_open = errors = 0

    async with AsyncSessionLocal() as db:
        try:
            entries = (await db.execute(
                select(LedgerEntry)
                .where(LedgerEntry.source != "engine")
                .where(LedgerEntry.resolved_at.is_(None))
                .where(LedgerEntry.external_ref.isnot(None))
                .limit(MAX_PER_RUN)
            )).scalars().all()
        except Exception as exc:
            # Fresh DB / CI without Postgres / table missing: degrade, don't crash.
            logger.warning("external resolution: ledger read failed (%s)", exc)
            return {"resolved": 0, "still_open": 0, "errors": 0, "skipped": "db_unavailable"}

        for entry in entries:
            try:
                obs = await _resolve_one(entry)
                if obs is None:
                    still_open += 1
                    continue
                p = (entry.prediction_score or 0) / 100.0
                await db.execute(
                    update(LedgerEntry)
                    .where(LedgerEntry.id == entry.id)
                    .where(LedgerEntry.resolved_at.is_(None))  # never re-grade
                    .values(
                        outcome=_outcome_label(obs),
                        observed_probability=obs,
                        brier_score=calibration.brier_score(p, obs),
                        resolved_at=datetime.now(timezone.utc),
                    )
                )
                resolved += 1
            except Exception as exc:
                logger.error("external resolution error for %s: %s", entry.external_ref, exc)
                errors += 1

        await db.commit()

        db.add(PipelineMetric(
            id=uuid.uuid4(),
            worker_name="external_resolution_worker",
            errors=errors,
            duration_seconds=round(time.perf_counter() - start, 2),
        ))
        await db.commit()

    logger.info(
        "External resolution done: resolved=%d still_open=%d errors=%d duration=%.1fs",
        resolved, still_open, errors, time.perf_counter() - start,
    )
    return {"resolved": resolved, "still_open": still_open, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_external_resolution_worker())
