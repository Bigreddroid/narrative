"""
EXPOSURE SNAPSHOT — captures the current Exposure Index into exposure_snapshots.

Runs on an interval so the temporal layer (momentum/trend, analogs, pattern base
rates) has real accumulated history to read instead of modeled synthetic series.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from backend.api.routes.exposure import PAID_TIER_EVENT_LIMIT, _load_graph
from backend.consequence_engine import propagation
from backend.database import AsyncSessionLocal
from backend.models.exposure_snapshot import ExposureSnapshot

logger = logging.getLogger(__name__)

TOP_N = 15


async def run_exposure_snapshot_worker() -> dict:
    start = time.perf_counter()
    async with AsyncSessionLocal() as db:
        events, edges = await _load_graph(db, PAID_TIER_EVENT_LIMIT)
        if not events:
            return {"snapshotted": 0}
        model = propagation.compute_exposure_model(events, edges)
        now = datetime.now(timezone.utc)
        rows = [ExposureSnapshot(kind="pressure", entity_key="", score=model["pressure"], captured_at=now)]
        for s in model["sectors"][:TOP_N]:
            rows.append(ExposureSnapshot(kind="sector", entity_key=s["key"], score=s["score"], captured_at=now))
        for r in model["regions"][:TOP_N]:
            rows.append(ExposureSnapshot(kind="region", entity_key=r["key"], score=r["score"], captured_at=now))
        db.add_all(rows)
        await db.commit()

    logger.info("Exposure snapshot: %d rows in %.1fs", len(rows), time.perf_counter() - start)
    return {"snapshotted": len(rows)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_exposure_snapshot_worker())
