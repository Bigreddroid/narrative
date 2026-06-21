"""
Admin overrides — importance score overrides, suppression, re-analysis triggers.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.narrative_event import NarrativeEvent

logger = logging.getLogger(__name__)


async def override_importance_score(
    event_id: uuid.UUID,
    new_score: float,
    db: AsyncSession,
) -> None:
    event = await db.get(NarrativeEvent, event_id)
    if not event:
        raise ValueError(f"Event {event_id} not found")
    event.global_importance_score = new_score
    db.add(event)
    await db.flush()
    logger.info("Admin overrode importance score for %s → %.1f", event_id, new_score)


async def suppress_map(
    event_id: uuid.UUID,
    reason: str,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(EventConsequenceMap)
        .where(EventConsequenceMap.narrative_event_id == event_id)
        .order_by(EventConsequenceMap.version.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if not latest:
        raise ValueError(f"No consequence map found for event {event_id}")

    latest.is_suppressed = True
    latest.suppression_reason = reason
    db.add(latest)
    await db.flush()
    logger.info("Admin suppressed map for event %s: %s", event_id, reason)


async def restore_map(event_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(
        select(EventConsequenceMap)
        .where(EventConsequenceMap.narrative_event_id == event_id)
        .order_by(EventConsequenceMap.version.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if not latest:
        return

    latest.is_suppressed = False
    latest.suppression_reason = None
    db.add(latest)
    await db.flush()
    logger.info("Admin restored map for event %s", event_id)


async def queue_reanalysis(event_id: uuid.UUID, db: AsyncSession) -> None:
    event = await db.get(NarrativeEvent, event_id)
    if not event:
        raise ValueError(f"Event {event_id} not found")

    event.is_mapped = False
    event.is_importance_scored = True
    db.add(event)
    await db.flush()
    logger.info("Admin queued re-analysis for event %s", event_id)
