import hashlib

from fastapi import APIRouter
from sqlalchemy import select

from backend.api.dependencies import DbDep, UserDep
from backend.consequence_engine import evidence as ev
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

    limit = 10 if user.tier == "free" else 50

    # Both branches now carry the same two gates /events has always applied:
    # an event we cannot back up, and a duplicate folded into a canonical event,
    # are not feed items. Measured on the live corpus, 35.5% of the rows behind
    # this route's predicate were one or the other.
    if not cache or not cache.event_ids:
        # Fall back to global importance-ranked feed
        events_result = await db.execute(
            select(NarrativeEvent)
            .where(NarrativeEvent.is_mapped == True)
            .where(NarrativeEvent.merged_into_id.is_(None))
            .where(ev.evidenced())
            .order_by(NarrativeEvent.global_importance_score.desc())
            .limit(limit)
        )
        events = events_result.scalars().all()
    else:
        # The segment cache was BUILT from the unfiltered table, so its id list
        # still contains severed and merged rows — a personalised feed was the one
        # place the contamination survived every other fix. Gate the whole cached
        # list and slice AFTER, not before: slicing first and then filtering would
        # silently shrink a 50-item feed to whatever happened to survive in the
        # first 50 ids, so a reader's feed would get shorter the more duplicates
        # their segment collected.
        events_result = await db.execute(
            select(NarrativeEvent)
            .where(NarrativeEvent.id.in_(cache.event_ids))
            .where(NarrativeEvent.merged_into_id.is_(None))
            .where(ev.evidenced())
        )
        # Restore ranking order, then take the tier's slice.
        id_order = {eid: i for i, eid in enumerate(cache.event_ids)}
        events = sorted(events_result.scalars().all(),
                        key=lambda e: id_order.get(e.id, 10**9))[:limit]

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
