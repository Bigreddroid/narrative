"""
STEP 5 — CONSEQUENCE MAPPING (every 15 minutes)
THIS IS THE ONLY STEP THAT CALLS CLAUDE.
One call per cluster. Never per article.
Deep (>=70): full chain + evidence + prediction.
Light (40-69): summary + basic impact only.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.consequence_engine.consensus_mapper import map_cluster
from backend.consequence_engine.importance_scorer import get_mapping_depth
from backend.database import AsyncSessionLocal
from backend.models.article import Article
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.narrative_event import NarrativeEvent
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.source import Source

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_EVENTS_PER_RUN = 20
MAX_ARTICLES_PER_CLUSTER = 10


def _coerce_str_list(raw) -> list[str]:
    """Ensure every element is a plain string — Claude sometimes returns dicts."""
    if not raw:
        return []
    return [v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for v in raw]


async def map_event(event: NarrativeEvent, db: AsyncSession) -> dict | None:
    depth = get_mapping_depth(
        event.global_importance_score,
        settings.importance_threshold_deep,
        settings.importance_threshold_light,
    )

    if depth == "none":
        event.is_mapped = True
        db.add(event)
        return None

    articles_result = await db.execute(
        select(Article, Source)
        .join(Source, Article.source_id == Source.id, isouter=True)
        .where(Article.narrative_event_id == event.id)
        .order_by(Article.importance_score.desc())
        .limit(MAX_ARTICLES_PER_CLUSTER)
    )
    rows = articles_result.all()

    if not rows:
        event.is_mapped = True
        db.add(event)
        return None

    article_dicts = [
        {
            "title": article.title,
            "content": article.content or "",
            "source_name": source.name if source else "Unknown",
            "bias_rating": source.bias_rating if source else "unknown",
        }
        for article, source in rows
    ]

    try:
        result = await asyncio.to_thread(map_cluster, article_dicts, depth, "global")
        if asyncio.iscoroutine(result):
            result = await result
    except Exception as exc:
        logger.error("Claude mapping failed for event %s: %s", event.id, exc)
        return None

    meta = result.pop("_meta", {})

    event.canonical_title       = result.get("canonical_title", event.canonical_title)
    event.canonical_summary     = result.get("canonical_summary")
    event.category              = result.get("category")
    event.global_importance_score = float(result.get("global_importance_score", event.global_importance_score))
    event.current_status        = result.get("current_status", "developing")
    event.affected_sectors      = _coerce_str_list(result.get("affected_sectors"))
    event.affected_professions  = _coerce_str_list(result.get("affected_professions"))
    event.geographic_relevance  = _coerce_str_list(result.get("geographic_relevance"))
    event.follow_keywords       = _coerce_str_list(result.get("follow_keywords"))
    event.is_mapped             = True
    event.last_updated_at       = datetime.now(timezone.utc)

    geo = result.get("geo_centroid")
    if geo:
        event.geo_centroid_lat = geo.get("lat")
        event.geo_centroid_lng = geo.get("lng")

    db.add(event)

    latest_version_result = await db.execute(
        select(EventConsequenceMap)
        .where(EventConsequenceMap.narrative_event_id == event.id)
        .order_by(EventConsequenceMap.version.desc())
        .limit(1)
    )
    latest = latest_version_result.scalar_one_or_none()
    next_version = (latest.version + 1) if latest else 1

    consequence_map = EventConsequenceMap(
        id=uuid.uuid4(),
        narrative_event_id=event.id,
        version=next_version,
        consensus_summary=result.get("consensus"),
        disputed_points=_coerce_str_list(result.get("disputed")),  # TEXT[] — must be List[str]
        consequence_chain=result.get("consequence_chain") or [],
        direct_impact=result.get("direct_impact"),
        indirect_impact=result.get("indirect_impact"),
        prediction_score=result.get("prediction_score"),
        prediction_reasoning=result.get("prediction_reasoning"),
        confidence=result.get("confidence"),
        sources_analyzed=[a["source_name"] for a in article_dicts],
    )
    db.add(consequence_map)
    await db.flush()

    for article, _ in rows:
        article.is_processed  = True
        article.processed_at  = datetime.now(timezone.utc)
        db.add(article)

    return meta


async def run_mapping_worker() -> dict:
    start = time.perf_counter()
    events_mapped = 0
    claude_calls  = 0
    claude_tokens = 0
    claude_cost   = 0.0
    errors        = 0

    # Fetch event IDs to process (separate session — no shared state)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(NarrativeEvent.id)
            .where(NarrativeEvent.is_importance_scored == True)
            .where(NarrativeEvent.is_mapped == False)
            .order_by(NarrativeEvent.global_importance_score.desc())
            .limit(MAX_EVENTS_PER_RUN)
        )
        event_ids = [row[0] for row in result.all()]

    # Each event gets its own session/transaction so one bad event never rolls back the rest
    for event_id in event_ids:
        try:
            async with AsyncSessionLocal() as db:
                event_result = await db.execute(
                    select(NarrativeEvent).where(NarrativeEvent.id == event_id)
                )
                event = event_result.scalar_one_or_none()
                if not event or event.is_mapped:
                    continue
                meta = await map_event(event, db)
                await db.commit()

            if meta:
                claude_calls  += 1
                claude_tokens += meta.get("input_tokens", 0) + meta.get("output_tokens", 0)
                claude_cost   += meta.get("cost_usd", 0.0)
            events_mapped += 1

        except Exception as exc:
            logger.error("Mapping worker error for event %s: %s", event_id, exc)
            errors += 1

    # Record metrics in its own session
    async with AsyncSessionLocal() as db:
        duration = time.perf_counter() - start
        metric = PipelineMetric(
            id=uuid.uuid4(),
            worker_name="mapping_worker",
            events_mapped=events_mapped,
            claude_calls=claude_calls,
            claude_tokens_used=claude_tokens,
            claude_cost_usd=claude_cost,
            errors=errors,
            duration_seconds=round(duration, 2),
        )
        db.add(metric)
        await db.commit()

        try:
            from backend.services.cost_alert import check_and_alert_daily_cost
            await check_and_alert_daily_cost(db)
        except Exception:
            pass

    logger.info(
        "Mapping worker done: events=%d claude_calls=%d cost=$%.4f errors=%d",
        events_mapped, claude_calls, claude_cost, errors,
    )
    return {
        "events_mapped": events_mapped,
        "claude_calls": claude_calls,
        "claude_cost_usd": claude_cost,
        "errors": errors,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_mapping_worker())
