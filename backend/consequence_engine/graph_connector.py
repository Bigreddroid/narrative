"""
LEAN for dual customer + enterprise Bloomberg terminal.
Basic overlap connections only (for "related events" in terminal).
Heavy graph / evolution / full consequence mapping is stretch (enterprise only later).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.event_connection import EventConnection
from backend.models.narrative_event import NarrativeEvent

logger = logging.getLogger(__name__)
settings = get_settings()


def _overlap_score(list_a: list[str] | None, list_b: list[str] | None) -> tuple[float, list[str]]:
    if not list_a or not list_b:
        return 0.0, []
    set_a = {s.lower() for s in list_a}
    set_b = {s.lower() for s in list_b}
    shared = set_a & set_b
    if not shared:
        return 0.0, []
    union = set_a | set_b
    score = len(shared) / len(union)
    return score, sorted(shared)


def compute_connection_weight(event_a: NarrativeEvent, event_b: NarrativeEvent) -> dict[str, Any] | None:
    sector_score, shared_sectors = _overlap_score(
        event_a.affected_sectors, event_b.affected_sectors
    )
    geo_score, shared_geo = _overlap_score(
        event_a.geographic_relevance, event_b.geographic_relevance
    )
    keyword_score, _ = _overlap_score(
        event_a.follow_keywords, event_b.follow_keywords
    )

    weight = (sector_score * 0.5) + (geo_score * 0.3) + (keyword_score * 0.2)

    if weight < settings.graph_connection_threshold:
        return None

    connection_type = "shared_sector"
    if geo_score > sector_score:
        connection_type = "shared_geography"
    if sector_score > 0 and geo_score > 0:
        connection_type = "shared_sector"

    shared_context_parts = []
    if shared_sectors:
        shared_context_parts.append(f"sectors: {', '.join(shared_sectors[:3])}")
    if shared_geo:
        shared_context_parts.append(f"regions: {', '.join(shared_geo[:3])}")
    shared_context = "Connected via " + " and ".join(shared_context_parts) if shared_context_parts else ""

    return {
        "connection_type": connection_type,
        "connection_weight": round(weight, 3),
        "shared_sectors": shared_sectors,
        "shared_geography": shared_geo,
        "shared_context": shared_context,
    }


async def compute_connections_for_event(
    event: NarrativeEvent, db: AsyncSession
) -> int:
    """
    Compute connections between this event and all other mapped events.
    Returns number of connections created or updated.
    """
    all_events_result = await db.execute(
        select(NarrativeEvent)
        .where(NarrativeEvent.id != event.id)
        .where(NarrativeEvent.is_mapped == True)
    )
    all_events = all_events_result.scalars().all()

    connections_created = 0

    for other in all_events:
        connection_data = compute_connection_weight(event, other)
        if not connection_data:
            continue

        # Check if connection already exists (either direction)
        existing = await db.execute(
            select(EventConnection).where(
                (
                    (EventConnection.event_a_id == event.id) &
                    (EventConnection.event_b_id == other.id)
                ) | (
                    (EventConnection.event_a_id == other.id) &
                    (EventConnection.event_b_id == event.id)
                )
            )
        )
        existing_conn = existing.scalar_one_or_none()

        if existing_conn:
            existing_conn.connection_weight = connection_data["connection_weight"]
            existing_conn.shared_sectors = connection_data["shared_sectors"]
            existing_conn.shared_geography = connection_data["shared_geography"]
            existing_conn.shared_context = connection_data["shared_context"]
            existing_conn.updated_at = datetime.now(timezone.utc)
            db.add(existing_conn)
        else:
            conn = EventConnection(
                id=uuid.uuid4(),
                event_a_id=event.id,
                event_b_id=other.id,
                **connection_data,
            )
            db.add(conn)
            connections_created += 1

    await db.flush()

    event.is_graph_connected = True
    db.add(event)

    logger.info(
        "Connections computed for event '%s': %d new",
        event.canonical_title[:60],
        connections_created,
    )
    return connections_created
