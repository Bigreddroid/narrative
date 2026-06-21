"""
STEP 3 — CLUSTER (every 30 minutes)
pgvector cosine similarity >= 0.82.
No AI. Pure vector math.
"""

import asyncio
import logging
import time
import uuid

from backend.consequence_engine.clusterer import cluster_unprocessed_articles
from backend.database import AsyncSessionLocal
from backend.models.pipeline_metrics import PipelineMetric

logger = logging.getLogger(__name__)


async def run_cluster_worker() -> dict:
    start = time.perf_counter()

    async with AsyncSessionLocal() as db:
        processed, new_events = await cluster_unprocessed_articles(db)
        await db.commit()

        duration = time.perf_counter() - start
        metric = PipelineMetric(
            id=uuid.uuid4(),
            worker_name="cluster_worker",
            clusters_created=new_events,
            duration_seconds=round(duration, 2),
        )
        db.add(metric)
        await db.commit()

    logger.info(
        "Cluster worker done: processed=%d new_events=%d duration=%.1fs",
        processed,
        new_events,
        time.perf_counter() - start,
    )
    return {"processed": processed, "new_events": new_events}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_cluster_worker())
