"""
Detects when a narrative_event has materially changed
and creates event_revisions.
Triggers re-mapping via Claude when warranted.
"""

import logging
import uuid
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.article import Article
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.event_revision import EventRevision
from backend.models.narrative_event import NarrativeEvent

logger = logging.getLogger(__name__)
settings = get_settings()

EMBEDDING_DRIFT_THRESHOLD = 0.15
HIGH_IMPORTANCE_RESCORE_THRESHOLD = 80.0


def _cosine_distance(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    norm_a, norm_b = np.linalg.norm(va), np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return float(1.0 - np.dot(va, vb) / (norm_a * norm_b))


async def check_for_evolution(
    event: NarrativeEvent,
    db: AsyncSession,
) -> bool:
    """
    Check if an event has evolved enough to warrant re-mapping.
    Returns True if evolution detected.
    """
    # Get new high-importance articles for this event
    new_articles_result = await db.execute(
        select(Article)
        .where(Article.narrative_event_id == event.id)
        .where(Article.is_processed == False)
        .where(Article.importance_score >= HIGH_IMPORTANCE_RESCORE_THRESHOLD)
        .limit(5)
    )
    new_high_importance = new_articles_result.scalars().all()

    if new_high_importance:
        logger.info(
            "Event '%s': %d new high-importance articles — triggering evolution",
            event.canonical_title[:60],
            len(new_high_importance),
        )
        return True

    # Check embedding drift from current event embedding
    if event.embedding is None:
        return False

    new_articles_with_embedding_result = await db.execute(
        select(Article)
        .where(Article.narrative_event_id == event.id)
        .where(Article.is_processed == False)
        .where(Article.embedding.isnot(None))
        .limit(10)
    )
    new_articles_with_embedding = new_articles_with_embedding_result.scalars().all()

    if not new_articles_with_embedding:
        return False

    embeddings = [a.embedding for a in new_articles_with_embedding if a.embedding]
    if not embeddings:
        return False

    avg_new_embedding = np.mean([np.array(e) for e in embeddings], axis=0).tolist()
    drift = _cosine_distance(event.embedding, avg_new_embedding)

    if drift > EMBEDDING_DRIFT_THRESHOLD:
        logger.info(
            "Event '%s': embedding drift %.3f > %.3f — triggering evolution",
            event.canonical_title[:60],
            drift,
            EMBEDDING_DRIFT_THRESHOLD,
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
