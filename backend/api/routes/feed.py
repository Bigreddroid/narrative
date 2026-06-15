import hashlib

from fastapi import APIRouter
from sqlalchemy import select

from backend.api.dependencies import DbDep, UserDep
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.narrative_event import NarrativeEvent
from backend.models.segment_feed_cache import SegmentFeedCache

router = APIRouter(prefix="/feed", tags=["feed"])


def _segment_key(country: str, profession: str, sectors: list[str]) -> str:
    raw = f"{country}|{profession}|{','.join(sorted(sectors))}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


@router.get("/")
async def get_feed(
    db: DbDep,
    user: UserDep,
) -> dict:
    key = _segment_key(
        user.country or "",
        user.profession or "",
        user.spending_categories or [],
    )

    cache_result = await db.execute(
        select(SegmentFeedCache).where(SegmentFeedCache.segment_key == key)
    )
    cache = cache_result.scalar_one_or_none()

    if not cache or not cache.event_ids:
        # Fall back to global importance-ranked feed
        events_result = await db.execute(
            select(NarrativeEvent)
            .where(NarrativeEvent.is_mapped == True)
            .order_by(NarrativeEvent.global_importance_score.desc())
            .limit(10 if user.tier == "free" else 50)
        )
        events = events_result.scalars().all()
    else:
        limit = 10 if user.tier == "free" else 50
        event_ids = cache.event_ids[:limit]
        events_result = await db.execute(
            select(NarrativeEvent).where(NarrativeEvent.id.in_(event_ids))
        )
        events = events_result.scalars().all()
        # Restore ranking order
        id_order = {eid: i for i, eid in enumerate(event_ids)}
        events = sorted(events, key=lambda e: id_order.get(e.id, 999))

    feed_items = []
    for event in events:
        map_result = await db.execute(
            select(EventConsequenceMap)
            .where(EventConsequenceMap.narrative_event_id == event.id)
            .where(EventConsequenceMap.is_suppressed == False)
            .order_by(EventConsequenceMap.version.desc())
            .limit(1)
        )
        latest_map = map_result.scalar_one_or_none()

        item = {
            "id": str(event.id),
            "canonical_title": event.canonical_title,
            "canonical_summary": event.canonical_summary,
            "category": event.category,
            "current_status": event.current_status,
            "global_importance_score": event.global_importance_score,
            "geo_centroid_lat": event.geo_centroid_lat,
            "geo_centroid_lng": event.geo_centroid_lng,
            "last_updated_at": event.last_updated_at.isoformat() if event.last_updated_at else None,
        }

        if latest_map:
            item["prediction_score"] = latest_map.prediction_score
            item["confidence"] = latest_map.confidence if user.tier != "free" else None
            item["direct_impact"] = latest_map.direct_impact

        feed_items.append(item)

    return {
        "feed": feed_items,
        "segment_key": key,
        "is_personalized": cache is not None,
        "built_at": cache.built_at.isoformat() if cache and cache.built_at else None,
    }


@router.get("/public")
async def get_public_feed(db: DbDep) -> dict:
    """Anonymous teaser for the landing page — top mapped events, no auth."""
    events = (await db.execute(
        select(NarrativeEvent)
        .where(NarrativeEvent.is_mapped == True)
        .order_by(NarrativeEvent.global_importance_score.desc())
        .limit(6)
    )).scalars().all()

    items = []
    for event in events:
        latest_map = (await db.execute(
            select(EventConsequenceMap)
            .where(EventConsequenceMap.narrative_event_id == event.id)
            .where(EventConsequenceMap.is_suppressed == False)
            .order_by(EventConsequenceMap.version.desc())
            .limit(1)
        )).scalar_one_or_none()

        impact = ""
        if latest_map and isinstance(latest_map.direct_impact, dict):
            impact = (latest_map.direct_impact.get("description") or "")[:90]

        items.append({
            "id": str(event.id),
            "title": event.canonical_title,
            "category": event.category,
            "importance": event.global_importance_score,
            "impact": impact,
        })

    return {"feed": items}
