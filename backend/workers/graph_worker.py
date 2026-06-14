"""
LEAN / STRETCH — Graph connections worker.
Basic connections now computed lightly on ingest where needed.
Full scheduled heavy graph is stretch for enterprise terminal density.
"""

import asyncio
import logging
import time
import uuid

from sqlalchemy import select

from backend.consequence_engine.graph_connector import compute_connections_for_event
from backend.database import AsyncSessionLocal
from backend.models.narrative_event import NarrativeEvent
from backend.models.pipeline_metrics import PipelineMetric

logger = logging.getLogger(__name__)


async def run_graph_worker() -> dict:
    start = time.perf_counter()
    connections_computed = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        events_result = await db.execute(
            select(NarrativeEvent)
            .where(NarrativeEvent.is_mapped == True)
            .where(NarrativeEvent.is_graph_connected == False)
            .limit(50)
        )
        events = events_result.scalars().all()

        for event in events:
            try:
                new_conns = await compute_connections_for_event(event, db)
                connections_computed += new_conns
            except Exception as exc:
                logger.error("Graph worker error for event %s: %s", event.id, exc)
                errors += 1

        await db.commit()

        duration = time.perf_counter() - start
        metric = PipelineMetric(
            id=uuid.uuid4(),
            worker_name="graph_worker",
            connections_computed=connections_computed,
            errors=errors,
            duration_seconds=round(duration, 2),
        )
        db.add(metric)
        await db.commit()

    logger.info(
        "Graph worker done: events=%d connections=%d errors=%d duration=%.1fs",
        len(events) if "events" in dir() else 0,
        connections_computed,
        errors,
        time.perf_counter() - start,
    )
    return {"connections_computed": connections_computed, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_graph_worker())
