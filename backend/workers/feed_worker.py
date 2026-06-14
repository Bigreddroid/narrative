"""
STEP 8 — FEED REBUILD (every 1 hour)
Segment key = hash(country + profession + sectors).
Ranked by relevance + importance + prediction urgency.
Never by engagement signals.
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text

from backend.database import AsyncSessionLocal
from backend.models.narrative_event import NarrativeEvent
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.segment_feed_cache import SegmentFeedCache
from backend.models.user import User

logger = logging.getLogger(__name__)

FEED_SIZE = 50


def _segment_key(country: str, profession: str, sectors: list[str]) -> str:
    raw = f"{country}|{profession}|{','.join(sorted(sectors))}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def build_feed_for_segment(
    country: str,
    profession: str,
    sectors: list[str],
    db,
) -> list[uuid.UUID]:
    """
    Rank events by:
    1. Sector overlap with user profile (0-1)
    2. global_importance_score (0-100)
    3. prediction_score urgency (high score + short timeline)
    Never by engagement signals.
    """
    events_result = await db.execute(
        select(NarrativeEvent)
        .where(NarrativeEvent.is_mapped == True)
        .where(NarrativeEvent.current_status != "resolved")
        .order_by(NarrativeEvent.global_importance_score.desc())
        .limit(500)
    )
    events = events_result.scalars().all()

    if not events:
        return []

    user_sectors = {s.lower() for s in sectors}
    user_geo = country.lower()

    scored_events = []
    for event in events:
        event_sectors = {s.lower() for s in (event.affected_sectors or [])}
        event_geo = [g.lower() for g in (event.geographic_relevance or [])]

        sector_overlap = len(user_sectors & event_sectors) / max(len(user_sectors | event_sectors), 1)
        geo_relevance = 1.0 if user_geo in event_geo else 0.0

        importance_norm = event.global_importance_score / 100.0

        # Get latest prediction score
        latest_map_result = await db.execute(
            text("""
                SELECT prediction_score FROM event_consequence_maps
                WHERE narrative_event_id = :eid
                  AND is_suppressed = FALSE
                ORDER BY version DESC
                LIMIT 1
            """),
            {"eid": event.id},
        )
        pred_row = latest_map_result.fetchone()
        prediction_norm = (pred_row[0] or 0) / 100.0 if pred_row else 0.0

        score = (
            sector_overlap * 0.35
            + geo_relevance * 0.25
            + importance_norm * 0.25
            + prediction_norm * 0.15
        )

        scored_events.append((score, event.id))

    scored_events.sort(key=lambda x: x[0], reverse=True)
    return [eid for _, eid in scored_events[:FEED_SIZE]]


async def run_feed_worker() -> dict:
    start = time.perf_counter()
    feeds_built = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        users_result = await db.execute(select(User))
        users = users_result.scalars().all()

        seen_segments = set()

        for user in users:
            try:
                key = _segment_key(
                    user.country or "",
                    user.profession or "",
                    user.spending_categories or [],
                )

                if key in seen_segments:
                    continue
                seen_segments.add(key)

                event_ids = await build_feed_for_segment(
                    user.country or "",
                    user.profession or "",
                    user.spending_categories or [],
                    db,
                )

                existing = await db.execute(
                    select(SegmentFeedCache).where(SegmentFeedCache.segment_key == key)
                )
                cache = existing.scalar_one_or_none()

                if cache:
                    cache.event_ids = event_ids
                    cache.built_at = datetime.now(timezone.utc)
                    db.add(cache)
                else:
                    cache = SegmentFeedCache(
                        id=uuid.uuid4(),
                        segment_key=key,
                        event_ids=event_ids,
                        built_at=datetime.now(timezone.utc),
                    )
                    db.add(cache)

                feeds_built += 1

            except Exception as exc:
                logger.error("Feed build error for user %s: %s", user.id, exc)
                errors += 1

        await db.commit()

        duration = time.perf_counter() - start
        metric = PipelineMetric(
            id=uuid.uuid4(),
            worker_name="feed_worker",
            errors=errors,
            duration_seconds=round(duration, 2),
        )
        db.add(metric)
        await db.commit()

    logger.info(
        "Feed worker done: segments=%d errors=%d duration=%.1fs",
        feeds_built,
        errors,
        time.perf_counter() - start,
    )
    return {"feeds_built": feeds_built, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_feed_worker())
