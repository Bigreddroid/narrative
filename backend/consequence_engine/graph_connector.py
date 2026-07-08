"""
Computes connections between narrative_events for the world map graph.
Pure logic — no AI. Connection strength = IDF-weighted overlap of sectors,
geography, and keywords; edges are directed by time (earlier event = cause).

The IDF weighting (see graph_scoring.py) means a shared *rare* sector signals a
much stronger link than a shared ubiquitous token like "United States". Directed
edges feed the CPE's downstream causal propagation.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.consequence_engine import graph_scoring
from backend.models.event_connection import EventConnection
from backend.models.narrative_event import NarrativeEvent

logger = logging.getLogger(__name__)
settings = get_settings()


def _build_idf_context(corpus: list[NarrativeEvent]) -> dict[str, dict[str, float]]:
    """Per-dimension IDF tables over all mapped events."""
    return {
        "sector": graph_scoring.build_idf([e.affected_sectors for e in corpus]),
        "geo": graph_scoring.build_idf([e.geographic_relevance for e in corpus]),
        "keyword": graph_scoring.build_idf([e.follow_keywords for e in corpus]),
    }


def compute_connection_weight(
    event_a: NarrativeEvent,
    event_b: NarrativeEvent,
    idf: dict[str, dict[str, float]],
) -> dict[str, Any] | None:
    """IDF-weighted, directed connection between two events. None if below threshold."""
    sector_score, shared_sectors = graph_scoring.weighted_overlap(event_a.affected_sectors, event_b.affected_sectors, idf["sector"])
    geo_score, shared_geo = graph_scoring.weighted_overlap(event_a.geographic_relevance, event_b.geographic_relevance, idf["geo"])
    keyword_score, _ = graph_scoring.weighted_overlap(event_a.follow_keywords, event_b.follow_keywords, idf["keyword"])

    tag_blend = graph_scoring.blended_weight(sector_score, geo_score, keyword_score)
    # Semantic gate: shared tags only count when the two events are actually about the
    # same situation (embedding cosine ≥ SEMANTIC_FLOOR). Drops coincidental tag matches
    # (e.g. two unrelated Energy+US events) instead of asserting a causal edge from tags.
    cos = graph_scoring.cosine(event_a.embedding, event_b.embedding)
    weight = graph_scoring.semantic_adjust(tag_blend, cos)
    if weight is None or weight < settings.graph_connection_threshold:
        return None

    connection_type = "shared_geography" if geo_score > sector_score else "shared_sector"

    parts = []
    if shared_sectors:
        parts.append(f"sectors: {', '.join(shared_sectors[:3])}")
    if shared_geo:
        parts.append(f"regions: {', '.join(shared_geo[:3])}")
    shared_context = "Connected via " + " and ".join(parts) if parts else ""

    return {
        "connection_type": connection_type,
        "connection_weight": round(weight, 3),
        "shared_sectors": shared_sectors,
        "shared_geography": shared_geo,
        "shared_context": shared_context,
        "direction": graph_scoring.causal_direction(event_a.first_detected_at, event_b.first_detected_at),
        "weight_breakdown": {
            "sector": round(sector_score, 3),
            "geo": round(geo_score, 3),
            "keyword": round(keyword_score, 3),
            "cosine": round(cos, 3) if cos is not None else None,
            "blend": round(weight, 3),
        },
    }


async def compute_connections_for_event(event: NarrativeEvent, db: AsyncSession) -> int:
    """
    Compute connections between this event and all other mapped events.
    Returns number of connections created or updated.
    """
    corpus_result = await db.execute(
        select(NarrativeEvent).where(NarrativeEvent.is_mapped == True)  # noqa: E712
    )
    corpus = corpus_result.scalars().all()
    idf = _build_idf_context(corpus)
    others = [e for e in corpus if e.id != event.id]

    connections_created = 0

    for other in others:
        connection_data = compute_connection_weight(event, other, idf)
        if not connection_data:
            continue

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
            # `direction` is stored relative to (event_a_id, event_b_id); flip it
            # if the stored pair is in the opposite order to (event, other).
            stored_forward = existing_conn.event_a_id == event.id
            existing_conn.connection_weight = connection_data["connection_weight"]
            existing_conn.connection_type = connection_data["connection_type"]
            existing_conn.shared_sectors = connection_data["shared_sectors"]
            existing_conn.shared_geography = connection_data["shared_geography"]
            existing_conn.shared_context = connection_data["shared_context"]
            existing_conn.direction = _orient(connection_data["direction"], stored_forward)
            existing_conn.weight_breakdown = connection_data["weight_breakdown"]
            existing_conn.updated_at = datetime.now(timezone.utc)
            db.add(existing_conn)
        else:
            conn = EventConnection(id=uuid.uuid4(), event_a_id=event.id, event_b_id=other.id, **connection_data)
            db.add(conn)
            connections_created += 1

    await db.flush()

    event.is_graph_connected = True
    db.add(event)

    logger.info("Connections computed for event '%s': %d new", event.canonical_title[:60], connections_created)
    return connections_created


def _orient(direction: str | None, stored_forward: bool) -> str | None:
    """Flip a (event, other)-relative direction to the stored (a, b) order."""
    if direction is None or stored_forward:
        return direction
    return "b_to_a" if direction == "a_to_b" else "a_to_b"
