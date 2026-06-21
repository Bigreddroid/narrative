"""
STEP 7 — EVOLUTION CHECK (every 1 hour)
Detects material changes to existing events.
Re-runs Claude if drift detected or high-importance articles arrive.
Creates event_revisions.
Queues alerts for followers.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from backend.config import get_settings
from backend.consequence_engine.consensus_mapper import map_cluster
from backend.consequence_engine.evolution_tracker import check_for_evolution, create_revision
from backend.database import AsyncSessionLocal
from backend.models.article import Article
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.narrative_event import NarrativeEvent
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.source import Source

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_EVENTS_PER_RUN = 30
MAX_ARTICLES_PER_CLUSTER = 10


async def run_evolution_worker() -> dict:
    start = time.perf_counter()
    evolutions_detected = 0
    claude_calls = 0
    claude_cost = 0.0
    errors = 0

    async with AsyncSessionLocal() as db:
        # Check mapped events that have unprocessed new articles
        events_result = await db.execute(
            select(NarrativeEvent)
            .where(NarrativeEvent.is_mapped == True)
            .where(NarrativeEvent.current_status.in_(["developing", "escalating"]))
            .limit(MAX_EVENTS_PER_RUN)
        )
        events = events_result.scalars().all()

        for event in events:
            try:
                evolved = await check_for_evolution(event, db)
                if not evolved:
                    continue

                evolutions_detected += 1

                # Rebuild article cluster
                articles_result = await db.execute(
                    select(Article, Source)
                    .join(Source, Article.source_id == Source.id, isouter=True)
                    .where(Article.narrative_event_id == event.id)
                    .order_by(Article.importance_score.desc())
                    .limit(MAX_ARTICLES_PER_CLUSTER)
                )
                rows = articles_result.all()

                article_dicts = [
                    {
                        "title": a.title,
                        "content": a.content or "",
                        "source_name": s.name if s else "Unknown",
                        "bias_rating": s.bias_rating if s else "unknown",
                    }
                    for a, s in rows
                ]

                if not article_dicts:
                    continue

                depth = "deep" if event.global_importance_score >= settings.importance_threshold_deep else "light"

                result = await asyncio.to_thread(map_cluster, article_dicts, depth)
                if asyncio.iscoroutine(result):
                    result = await result

                meta = result.pop("_meta", {})
                claude_calls += 1
                claude_cost += meta.get("cost_usd", 0.0)

                # Update event
                event.canonical_summary = result.get("canonical_summary", event.canonical_summary)
                event.current_status = result.get("current_status", event.current_status)
                event.last_updated_at = datetime.now(timezone.utc)
                db.add(event)

                # Create new consequence map version
                latest_result = await db.execute(
                    select(EventConsequenceMap)
                    .where(EventConsequenceMap.narrative_event_id == event.id)
                    .order_by(EventConsequenceMap.version.desc())
                    .limit(1)
                )
                latest = latest_result.scalar_one_or_none()
                next_version = (latest.version + 1) if latest else 1

                new_map = EventConsequenceMap(
                    id=uuid.uuid4(),
                    narrative_event_id=event.id,
                    version=next_version,
                    consensus_summary=result.get("consensus"),
                    disputed_points=result.get("disputed") or [],
                    consequence_chain=result.get("consequence_chain") or [],
                    direct_impact=result.get("direct_impact"),
                    indirect_impact=result.get("indirect_impact"),
                    prediction_score=result.get("prediction_score"),
                    prediction_reasoning=result.get("prediction_reasoning"),
                    confidence=result.get("confidence"),
                    sources_analyzed=[a["source_name"] for a in article_dicts],
                )
                db.add(new_map)
                await db.flush()

                await create_revision(event, new_map, "evolution_worker", db)

                # Mark new articles as processed
                for article, _ in rows:
                    if not article.is_processed:
                        article.is_processed = True
                        article.processed_at = datetime.now(timezone.utc)
                        db.add(article)

            except Exception as exc:
                logger.error("Evolution worker error for event %s: %s", event.id, exc)
                errors += 1

        await db.commit()

        duration = time.perf_counter() - start
        metric = PipelineMetric(
            id=uuid.uuid4(),
            worker_name="evolution_worker",
            events_mapped=evolutions_detected,
            claude_calls=claude_calls,
            claude_cost_usd=claude_cost,
            errors=errors,
            duration_seconds=round(duration, 2),
        )
        db.add(metric)
        await db.commit()

    logger.info(
        "Evolution worker done: evolutions=%d claude_calls=%d cost=$%.4f errors=%d",
        evolutions_detected,
        claude_calls,
        claude_cost,
        errors,
    )
    return {
        "evolutions_detected": evolutions_detected,
        "claude_calls": claude_calls,
        "errors": errors,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_evolution_worker())
