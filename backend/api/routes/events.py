import math
import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from backend.api.dependencies import DbDep, UserDep
from backend.consequence_engine import corroboration
from backend.models.article import Article
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.event_revision import EventRevision
from backend.models.narrative_event import NarrativeEvent
from backend.models.source import Source
from backend.services import osint_enrich, osint_extract, source_reliability

router = APIRouter(prefix="/events", tags=["events"])


def _gate_paid_fields(data: dict, user_tier: str) -> dict:
    """Strip paid-only fields for free users."""
    if user_tier == "free":
        data.pop("indirect_impact", None)
        data.pop("prediction_reasoning", None)
        data.pop("confidence", None)
        chain = data.get("consequence_chain")
        if isinstance(chain, list):
            data["consequence_chain"] = chain[:2]
    return data


@router.get("/")
async def list_events(
    db: DbDep,
    user: UserDep,
    category: str | None = Query(None),
    status: str | None = Query(None),
    discipline: str | None = Query(None, description="INT discipline: HUMINT/SIGINT/IMINT/GEOINT/MASINT/FININT/CYBINT"),
    source_type: str | None = Query(None, description="'osint' = open-source/unverified only"),
    source_prefix: str | None = Query(None, description="event source prefix, e.g. 'wipro_demo' matches the seeded demo scenario sources"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
) -> dict:
    query = (
        select(NarrativeEvent)
        .where(NarrativeEvent.is_mapped == True)
        .where(NarrativeEvent.merged_into_id.is_(None))  # hide near-duplicates folded into a canonical event
    )

    if user.tier == "free":
        query = query.limit(10)
    else:
        query = query.limit(limit).offset(offset)

    if category:
        query = query.where(NarrativeEvent.category == category)
    elif not (discipline or source_prefix):
        # Cyber CVEs are niche/high-volume — keep them out of the headline feed
        # (still reachable via ?category=cyber, ?discipline=CYBINT, and surfaced as
        # exposure drivers). An explicit discipline or source filter (e.g. a CYBINT
        # view, or the demo scenario slice) wants them, so skip this exclusion
        # whenever discipline= or source_prefix= is requested.
        query = query.where(NarrativeEvent.category != "cyber")
    if status:
        query = query.where(NarrativeEvent.current_status == status)
    if discipline:
        query = query.where(NarrativeEvent.int_discipline == discipline)
    if source_type == "osint":
        query = query.where(NarrativeEvent.source.like("osint_%"))
    if source_prefix:
        query = query.where(NarrativeEvent.source.like(source_prefix + "%"))

    # Freshness-blended ranking: importance + up to +15 recency boost that decays
    # over ~a day, so just-ingested live feeds (quakes, floods, storms) interleave
    # with high-importance news instead of being buried by it.
    age_seconds = func.extract(
        "epoch", func.now() - func.coalesce(NarrativeEvent.last_updated_at, NarrativeEvent.first_detected_at)
    )
    rank = NarrativeEvent.global_importance_score + 15.0 * func.exp(-age_seconds / 86400.0)
    query = query.order_by(rank.desc())

    result = await db.execute(query)
    events = result.scalars().all()

    return {
        "events": [
            {
                "id": str(e.id),
                "canonical_title": e.canonical_title,
                "canonical_summary": e.canonical_summary,
                "category": e.category,
                "int_discipline": e.int_discipline,
                "global_importance_score": e.global_importance_score,
                "current_status": e.current_status,
                "affected_sectors": e.affected_sectors,
                "geographic_relevance": e.geographic_relevance,
                "geo_centroid_lat": e.geo_centroid_lat,
                "geo_centroid_lng": e.geo_centroid_lng,
                "source": e.source,
                "is_osint": (e.source or "").startswith("osint_"),
                "first_detected_at": e.first_detected_at.isoformat() if e.first_detected_at else None,
                "last_updated_at": e.last_updated_at.isoformat() if e.last_updated_at else None,
            }
            for e in events
        ],
        "total": len(events),
    }


async def _source_grade(db, event) -> dict | None:
    """NATO Admiralty grade for this ONE event's primary source, carrying its live
    corroboration count from geo+time convergence — the same deterministic engine
    (`corroboration.corroborate` + `source_reliability.grade`) that grades the
    view-scoped /corroboration set and the /wipro fusion strip. Surfacing it on the
    single-event drill-in answers the buyer's #1 pain (official-source verification)
    exactly where they inspect one event. Degrades to an uncorroborated grade (never
    500s) when the event lacks coordinates or a timestamp to converge on."""
    if not event.source:
        return None
    count, sources, index = 0, [], 0.0
    if (event.first_detected_at and event.geo_centroid_lat is not None
            and event.geo_centroid_lng is not None):
        window = timedelta(hours=corroboration.DEFAULT_WINDOW_HOURS)
        # Spatially bound the candidate query to a bounding box ~radius around the
        # event, so the true corroborators are always in the set — an unbounded
        # ±72h window on a busy feed holds thousands of events and a blind LIMIT
        # would sample past the actual siblings. corroborate() then applies the
        # exact haversine ≤ radius; the box is a generous superset of that circle.
        lat_pad = corroboration.DEFAULT_RADIUS_KM / 111.0
        lng_pad = corroboration.DEFAULT_RADIUS_KM / (
            111.0 * max(0.15, math.cos(math.radians(event.geo_centroid_lat))))
        rows = await db.execute(
            select(NarrativeEvent).where(
                NarrativeEvent.first_detected_at.between(
                    event.first_detected_at - window, event.first_detected_at + window),
                NarrativeEvent.geo_centroid_lat.between(
                    event.geo_centroid_lat - lat_pad, event.geo_centroid_lat + lat_pad),
                NarrativeEvent.geo_centroid_lng.between(
                    event.geo_centroid_lng - lng_pad, event.geo_centroid_lng + lng_pad),
                NarrativeEvent.geo_centroid_lng.isnot(None),
                NarrativeEvent.merged_into_id.is_(None),
            ).limit(500)
        )
        payload = [
            {
                "id": str(e.id),
                "source": e.source,
                "discipline": e.int_discipline,
                "lat": e.geo_centroid_lat,
                "lng": e.geo_centroid_lng,
                "ts": e.first_detected_at.timestamp() * 1000 if e.first_detected_at else None,
            }
            for e in rows.scalars().all()
        ]
        entry = corroboration.corroborate(payload).get(str(event.id))
        if entry:
            count, sources, index = entry["count"], entry["sources"], entry["index"]
    history = await source_reliability.source_history_map(db, [event.source])
    g = source_reliability.grade(event.source, count, history.get(event.source))
    g["corroboration"] = {"index": index, "count": count, "sources": sources}
    return g


# NOTE: must stay declared before the dynamic /{event_id} route below.
@router.get("/corroboration")
async def events_corroboration(
    db: DbDep,
    user: UserDep,
    ids: str = Query(..., description="comma-separated event ids — the window to corroborate over"),
) -> dict:
    """Cross-feed corroboration computed over exactly the given set of events.

    Same deterministic engine as /exposure, but scoped to the caller's window
    (e.g. the events currently in view) instead of the global top-importance
    slice — so convergence reflects what the client is actually looking at.
    """
    try:
        id_list = [uuid.UUID(x.strip()) for x in ids.split(",") if x.strip()][:200]
    except ValueError:
        raise HTTPException(status_code=422, detail="ids must be comma-separated UUIDs")
    if not id_list:
        return {"corroboration": {}}
    result = await db.execute(select(NarrativeEvent).where(NarrativeEvent.id.in_(id_list)))
    payload = [
        {
            "id": str(e.id),
            "source": e.source,
            "discipline": e.int_discipline,
            "lat": e.geo_centroid_lat,
            "lng": e.geo_centroid_lng,
            "ts": e.first_detected_at.timestamp() * 1000 if e.first_detected_at else None,
        }
        for e in result.scalars().all()
    ]
    corrob = corroboration.corroborate(payload)
    corrob = {k: v for k, v in corrob.items() if v["count"] > 0}
    # Attach NATO Admiralty grades server-side (same path as /exposure) so the chip
    # rides the view-scoped map — the /wipro fusion strip reads it straight off here
    # instead of falling back to the global /exposure slice.
    await source_reliability.attach_grades(db, corrob, payload)
    return {"corroboration": corrob}


@router.get("/{event_id}")
async def get_event(
    event_id: uuid.UUID,
    db: DbDep,
    user: UserDep,
) -> dict:
    event = await db.get(NarrativeEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    map_result = await db.execute(
        select(EventConsequenceMap)
        .where(EventConsequenceMap.narrative_event_id == event_id)
        .where(EventConsequenceMap.is_suppressed == False)
        .order_by(EventConsequenceMap.version.desc())
        .limit(1)
    )
    latest_map = map_result.scalar_one_or_none()

    data: dict[str, Any] = {
        "id": str(event.id),
        "canonical_title": event.canonical_title,
        "int_discipline": event.int_discipline,
        "canonical_summary": event.canonical_summary,
        "category": event.category,
        "global_importance_score": event.global_importance_score,
        "current_status": event.current_status,
        "affected_sectors": event.affected_sectors,
        "affected_professions": event.affected_professions,
        "geographic_relevance": event.geographic_relevance,
        "geo_centroid_lat": event.geo_centroid_lat,
        "geo_centroid_lng": event.geo_centroid_lng,
        "source": event.source,
        "is_osint": (event.source or "").startswith("osint_"),
        "follow_keywords": event.follow_keywords,
        "first_detected_at": event.first_detected_at.isoformat() if event.first_detected_at else None,
        "last_updated_at": event.last_updated_at.isoformat() if event.last_updated_at else None,
        "consequence_map": None,
    }

    if latest_map:
        map_data = {
            "version": latest_map.version,
            "consensus_summary": latest_map.consensus_summary,
            "disputed_points": latest_map.disputed_points,
            "consequence_chain": latest_map.consequence_chain,
            "direct_impact": latest_map.direct_impact,
            "indirect_impact": latest_map.indirect_impact,
            "prediction_score": latest_map.prediction_score,
            "prediction_reasoning": latest_map.prediction_reasoning,
            "confidence": latest_map.confidence,
            "sources_analyzed": latest_map.sources_analyzed,
            "created_at": latest_map.created_at.isoformat(),
        }
        data["consequence_map"] = _gate_paid_fields(map_data, user.tier)

    articles_result = await db.execute(
        select(Article, Source.name.label("source_name"))
        .outerjoin(Source, Article.source_id == Source.id)
        .where(Article.narrative_event_id == event_id)
        .order_by(Article.importance_score.desc())
        .limit(10)
    )
    data["articles"] = [
        {
            "title": row.Article.title,
            "url": row.Article.url,
            "source": row.source_name or "Unknown",
            "date": row.Article.published_at.strftime("%b %d") if row.Article.published_at else None,
        }
        for row in articles_result.all()
    ]

    data["source_grade"] = await _source_grade(db, event)

    return data


@router.get("/{event_id}/revisions")
async def get_event_revisions(
    event_id: uuid.UUID,
    db: DbDep,
    user: UserDep,
) -> dict:
    if user.tier == "free":
        raise HTTPException(status_code=402, detail="Paid subscription required")

    event = await db.get(NarrativeEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    result = await db.execute(
        select(EventRevision)
        .where(EventRevision.narrative_event_id == event_id)
        .order_by(EventRevision.version.asc())
    )
    revisions = result.scalars().all()

    return {
        "revisions": [
            {
                "version": r.version,
                "prediction_score": r.prediction_score,
                "confidence": r.confidence,
                "change_summary": r.change_summary,
                "triggered_by": r.triggered_by,
                "created_at": r.created_at.isoformat(),
            }
            for r in revisions
        ]
    }


@router.get("/{event_id}/osint")
async def get_event_osint(
    event_id: uuid.UUID,
    db: DbDep,
    user: UserDep,
) -> dict:
    """Server-side OSINT linking for an event: investigatable entities extracted
    from its title + summary + consequence-map prose, each tagged with its kind and
    whether live enrichment is available. Open to all tiers (the actual investigate/
    enrich pivots stay gated); free users see what's there but the pivots are locked."""
    event = await db.get(NarrativeEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    map_result = await db.execute(
        select(EventConsequenceMap)
        .where(EventConsequenceMap.narrative_event_id == event_id)
        .where(EventConsequenceMap.is_suppressed == False)
        .order_by(EventConsequenceMap.version.desc())
        .limit(1)
    )
    latest_map = map_result.scalar_one_or_none()
    map_blob = None
    if latest_map:
        map_blob = {
            "consensus_summary": latest_map.consensus_summary,
            "prediction_reasoning": latest_map.prediction_reasoning,
            "direct_impact": latest_map.direct_impact,
            "indirect_impact": latest_map.indirect_impact,
            "disputed_points": latest_map.disputed_points,
            "consequence_chain": latest_map.consequence_chain,
        }

    entities = osint_extract.entities_for_event(
        event.canonical_title, event.canonical_summary, map_blob
    )
    for e in entities:
        e["enrichable"] = e["kind"] in osint_enrich.ENRICHABLE_KINDS

    return {
        "event_id": str(event.id),
        "source": event.source,
        "is_osint": (event.source or "").startswith("osint_"),
        "entities": entities,
        "locked": user.tier == "free",
    }
