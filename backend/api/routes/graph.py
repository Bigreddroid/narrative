"""
World map + event graph API.
Returns all nodes and edges for the D3 world map.
"""

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select

from backend.api.dependencies import DbDep, UserDep
from backend.models.event_connection import EventConnection
from backend.models.narrative_event import NarrativeEvent

router = APIRouter(prefix="/graph", tags=["graph"])

FREE_TIER_NODE_LIMIT = 10
TRACE_FANOUT = 60  # strongest connections pulled around the root to form the trace neighborhood


@router.get("/world")
async def get_world_graph(
    db: DbDep,
    user: UserDep,
) -> dict:
    """Returns all nodes and edges for the world map."""
    node_limit = FREE_TIER_NODE_LIMIT if user.tier == "free" else 500

    events_result = await db.execute(
        select(NarrativeEvent)
        .where(NarrativeEvent.is_mapped == True)
        .where(NarrativeEvent.merged_into_id.is_(None))  # hide near-duplicates folded into a canonical event
        .where(NarrativeEvent.geo_centroid_lat.isnot(None))
        .where(NarrativeEvent.geo_centroid_lng.isnot(None))
        .order_by(NarrativeEvent.global_importance_score.desc())
        .limit(node_limit)
    )
    events = events_result.scalars().all()

    event_ids = {e.id for e in events}

    nodes = [
        {
            "id": str(e.id),
            "title": e.canonical_title,
            "category": e.category,
            "int_discipline": e.int_discipline,
            "status": e.current_status,
            "importance": e.global_importance_score,
            "lat": e.geo_centroid_lat,
            "lng": e.geo_centroid_lng,
            "affected_sectors": e.affected_sectors,
            "geographic_relevance": e.geographic_relevance,
        }
        for e in events
    ]

    if user.tier == "free":
        return {"nodes": nodes, "edges": [], "limited": True}

    # Fetch edges only between visible nodes
    edges_result = await db.execute(
        select(EventConnection)
        .where(EventConnection.event_a_id.in_(event_ids))
        .where(EventConnection.event_b_id.in_(event_ids))
        .order_by(EventConnection.connection_weight.desc())
        .limit(1000)
    )
    edges = edges_result.scalars().all()

    return {
        "nodes": nodes,
        "edges": [
            {
                "id": str(e.id),
                "source": str(e.event_a_id),
                "target": str(e.event_b_id),
                "type": e.connection_type,
                "weight": e.connection_weight,
                "shared_sectors": e.shared_sectors,
                "shared_geography": e.shared_geography,
                "shared_context": e.shared_context,
            }
            for e in edges
        ],
        "limited": False,
    }


@router.get("/event/{event_id}")
async def get_event_graph(
    event_id: uuid.UUID,
    db: DbDep,
    user: UserDep,
) -> dict:
    """Returns the consequence graph for a specific event (for EventGraph component)."""
    event = await db.get(NarrativeEvent, event_id)
    if not event:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Event not found")

    connections_result = await db.execute(
        select(EventConnection)
        .where(
            (EventConnection.event_a_id == event_id) |
            (EventConnection.event_b_id == event_id)
        )
        .order_by(EventConnection.connection_weight.desc())
        .limit(20)
    )
    connections = connections_result.scalars().all()

    connected_ids = set()
    for c in connections:
        connected_ids.add(c.event_a_id)
        connected_ids.add(c.event_b_id)
    connected_ids.discard(event_id)

    connected_events_result = await db.execute(
        select(NarrativeEvent).where(NarrativeEvent.id.in_(connected_ids))
    )
    connected_events = connected_events_result.scalars().all()

    return {
        "root": {
            "id": str(event.id),
            "title": event.canonical_title,
            "category": event.category,
            "status": event.current_status,
            "importance": event.global_importance_score,
        },
        "connected_events": [
            {
                "id": str(e.id),
                "title": e.canonical_title,
                "category": e.category,
            "int_discipline": e.int_discipline,
                "status": e.current_status,
            }
            for e in connected_events
        ],
        "connections": [
            {
                "source": str(c.event_a_id),
                "target": str(c.event_b_id),
                "weight": c.connection_weight,
                "type": c.connection_type,
                "shared_context": c.shared_context,
                # cause→effect label relative to (source, target): a_to_b | b_to_a | null
                "direction": c.direction,
            }
            for c in connections
        ],
    }


@router.get("/event/{event_id}/trace")
async def get_consequence_trace(
    event_id: uuid.UUID,
    db: DbDep,
    user: UserDep,
    depth: int = Query(3, ge=1, le=4),
    max_nodes: int = Query(25, ge=1, le=60),
    grounded_only: bool = Query(False),
) -> dict:
    """Directed, multi-hop consequence chain FROM this event.

    Walks the event graph forward (cause→effect) to surface how the event's
    consequences cascade to other events. Each hop is labelled with its mechanism
    (shared sectors/regions) and its ``kind``/``grounded`` flag: grounded hops are
    real consequence links (semantic / geographic / specific-sector); co-occurrence
    hops rest only on generic shared tags. ``grounded_only=true`` drops the weak
    coincidences. Deterministic — no LLM. Returns an honest empty trace
    (limited=True) when the event has no outgoing links."""
    from backend.api.routes.exposure import _load_graph
    from backend.consequence_engine.tracer import trace_consequences

    root = await db.get(NarrativeEvent, event_id)
    if not root:
        raise HTTPException(status_code=404, detail="Event not found")

    # Bounded neighbourhood: the root plus the events on its strongest connections,
    # so the tracer can walk 2–3 hops among them without loading the whole graph.
    neigh = (await db.execute(
        select(EventConnection.event_a_id, EventConnection.event_b_id)
        .where(or_(EventConnection.event_a_id == event_id,
                   EventConnection.event_b_id == event_id))
        .order_by(EventConnection.connection_weight.desc())
        .limit(TRACE_FANOUT)
    )).all()
    ids = {event_id}
    for a, b in neigh:
        ids.add(a)
        ids.add(b)

    events, edges = await _load_graph(db, len(ids), event_ids=[str(i) for i in ids])
    trace = trace_consequences(str(event_id), events, edges, depth=depth,
                               max_nodes=max_nodes, grounded_only=grounded_only)
    trace["depth"] = depth
    return trace
