"""
Detects when a narrative_event has materially changed
and creates event_revisions.
Triggers re-mapping via Claude when warranted.
"""

import logging
import uuid
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.consequence_engine import evolution_logic
from backend.models.article import Article
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.event_revision import EventRevision
from backend.models.narrative_event import NarrativeEvent

logger = logging.getLogger(__name__)
settings = get_settings()

HIGH_IMPORTANCE_RESCORE_THRESHOLD = 80.0


def _cosine_distance(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    norm_a, norm_b = np.linalg.norm(va), np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return float(1.0 - np.dot(va, vb) / (norm_a * norm_b))


async def _embedding_drift(event: NarrativeEvent, db: AsyncSession) -> float:
    """Cosine drift between the event centroid and the mean of new article embeddings."""
    if event.embedding is None:
        return 0.0
    rows = (await db.execute(
        select(Article)
        .where(Article.narrative_event_id == event.id)
        .where(Article.is_processed == False)  # noqa: E712
        .where(Article.embedding.isnot(None))
        .limit(10)
    )).scalars().all()
    embeddings = [a.embedding for a in rows if a.embedding]
    if not embeddings:
        return 0.0
    avg_new = np.mean([np.array(e) for e in embeddings], axis=0).tolist()
    return _cosine_distance(event.embedding, avg_new)


async def check_for_evolution(
    event: NarrativeEvent,
    db: AsyncSession,
) -> bool:
    """Re-map when combined drift + new-article pressure exceeds the staleness- and
    category-adjusted threshold. Returns True if evolution detected.
    """
    n_high = (await db.execute(
        select(func.count())
        .select_from(Article)
        .where(Article.narrative_event_id == event.id)
        .where(Article.is_processed == False)  # noqa: E712
        .where(Article.importance_score >= HIGH_IMPORTANCE_RESCORE_THRESHOLD)
    )).scalar() or 0

    drift = await _embedding_drift(event, db)

    pressure = evolution_logic.evolution_pressure(
        drift, n_high, settings.evolution_volume_weight, settings.evolution_volume_tau
    )
    last = event.last_updated_at or event.first_detected_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    hours_since = (datetime.now(timezone.utc) - last).total_seconds() / 3600.0 if last else None
    threshold = evolution_logic.effective_threshold(
        settings.evolution_base_threshold, hours_since, event.category, settings.evolution_staleness_tau_hours
    )

    if evolution_logic.should_remap(pressure, threshold):
        logger.info(
            "Event '%s': evolution pressure %.3f ≥ threshold %.3f (drift=%.3f, new_high=%d) — re-mapping",
            event.canonical_title[:60], pressure, threshold, drift, n_high,
        )
        return True
    return False


async def create_revision(
    event: NarrativeEvent,
    new_map: EventConsequenceMap,
    triggered_by: str,
    db: AsyncSession,
) -> EventRevision:
    """Snapshot the current state of the event as a revision."""
    version_result = await db.execute(
        select(EventRevision)
        .where(EventRevision.narrative_event_id == event.id)
        .order_by(EventRevision.version.desc())
        .limit(1)
    )
    latest = version_result.scalar_one_or_none()
    next_version = (latest.version + 1) if latest else 1

    revision = EventRevision(
        id=uuid.uuid4(),
        narrative_event_id=event.id,
        version=next_version,
        consequence_chain=new_map.consequence_chain,
        prediction_score=new_map.prediction_score,
        confidence=new_map.confidence,
        change_summary=f"Version {next_version}: {triggered_by}",
        triggered_by=triggered_by,
        created_at=datetime.now(timezone.utc),
    )
    db.add(revision)

    event.last_updated_at = datetime.now(timezone.utc)
    db.add(event)

    await db.flush()
    logger.info(
        "Created revision v%d for event '%s'",
        next_version,
        event.canonical_title[:60],
    )
    return revision
