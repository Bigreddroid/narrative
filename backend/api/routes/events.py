import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from backend.api.dependencies import DbDep, UserDep
from backend.models.article import Article
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.event_revision import EventRevision
from backend.models.narrative_event import NarrativeEvent
from backend.models.source import Source

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
    limit: int = Query(20, le=100),
    offset: int = Query(0),
) -> dict:
    query = select(NarrativeEvent).where(NarrativeEvent.is_mapped == True)

    if user.tier == "free":
        query = query.limit(10)
    else:
        query = query.limit(limit).offset(offset)

    if category:
        query = query.where(NarrativeEvent.category == category)
    if status:
        query = query.where(NarrativeEvent.current_status == status)

    query = query.order_by(NarrativeEvent.global_importance_score.desc())

    result = await db.execute(query)
    events = result.scalars().all()

    return {
        "events": [
            {
                "id": str(e.id),
                "canonical_title": e.canonical_title,
                "canonical_summary": e.canonical_summary,
                "category": e.category,
                "global_importance_score": e.global_importance_score,
                "current_status": e.current_status,
                "affected_sectors": e.affected_sectors,
                "geographic_relevance": e.geographic_relevance,
                "geo_centroid_lat": e.geo_centroid_lat,
                "geo_centroid_lng": e.geo_centroid_lng,
                "first_detected_at": e.first_detected_at.isoformat() if e.first_detected_at else None,
                "last_updated_at": e.last_updated_at.isoformat() if e.last_updated_at else None,
            }
            for e in events
        ],
        "total": len(events),
    }


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
        "canonical_summary": event.canonical_summary,
        "category": event.category,
        "global_importance_score": event.global_importance_score,
        "current_status": event.current_status,
        "affected_sectors": event.affected_sectors,
        "affected_professions": event.affected_professions,
        "geographic_relevance": event.geographic_relevance,
        "geo_centroid_lat": event.geo_centroid_lat,
        "geo_centroid_lng": event.geo_centroid_lng,
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
