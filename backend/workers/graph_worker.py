"""
STEP 6 — GRAPH CONNECTIONS (every 1 hour)
Computes event_connections for all newly mapped events.
Powers the world map edge layer entirely.
"""

import asyncio
import logging
import time
import uuid

from sqlalchemy import select

from backend.consequence_engine.embedder import embed_texts
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
        # Backfill embeddings for mapped events that lack one. The graph connector's
        # semantic gate needs BOTH endpoints' embeddings, so an unembedded corpus
        # silently degrades every link to tag-only (and drops moderate-overlap links).
        # Events created before this backfill — or on paths that don't embed — are
        # healed here with the local ($0) embedder before we connect. Off-loaded to a
        # thread so a ~minute of CPU embedding doesn't stall the other workers.
        to_embed = (await db.execute(
            select(NarrativeEvent)
            .where(NarrativeEvent.is_mapped == True)
            .where(NarrativeEvent.embedding.is_(None))
            .limit(500)
        )).scalars().all()
        if to_embed:
            texts = [f"{e.canonical_title}. {e.canonical_summary or ''}".strip() for e in to_embed]
            try:
                vecs = await asyncio.to_thread(embed_texts, texts)
                for e, v in zip(to_embed, vecs):
                    e.embedding = v
                    db.add(e)
                await db.commit()
                logger.info("Graph worker: backfilled %d event embeddings", len(to_embed))
            except Exception as exc:  # noqa: BLE001 — backfill must not sink the worker
                logger.error("Graph worker embedding backfill failed: %s", exc)
                await db.rollback()

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
