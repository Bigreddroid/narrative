from fastapi import APIRouter, Query
from sqlalchemy import or_, select

from backend.api.dependencies import DbDep, UserDep
from backend.models.narrative_event import NarrativeEvent

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/")
async def search_events(
    db: DbDep,
    user: UserDep,
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(30, le=50),
) -> dict:
    cap = 10 if user.tier == "free" else min(limit, 50)
    pat = f"%{q}%"

    result = await db.execute(
        select(NarrativeEvent)
        .where(NarrativeEvent.is_mapped == True)
        .where(
            or_(
                NarrativeEvent.canonical_title.ilike(pat),
                NarrativeEvent.canonical_summary.ilike(pat),
                NarrativeEvent.category.ilike(pat),
            )
        )
        .order_by(NarrativeEvent.global_importance_score.desc())
        .limit(cap)
    )
    events = result.scalars().all()

    return {
        "query": q,
        "total": len(events),
        "events": [
            {
                "id": str(e.id),
                "canonical_title": e.canonical_title,
                "canonical_summary": e.canonical_summary,
                "category": e.category,
                "current_status": e.current_status,
                "global_importance_score": e.global_importance_score,
                "geographic_relevance": e.geographic_relevance,
                "geo_centroid_lat": e.geo_centroid_lat,
                "geo_centroid_lng": e.geo_centroid_lng,
                "first_detected_at": e.first_detected_at.isoformat() if e.first_detected_at else None,
            }
            for e in events
        ],
    }
