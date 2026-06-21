import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.dependencies import DbDep, UserDep
from backend.models.narrative_event import NarrativeEvent
from backend.models.user import UserFollow

router = APIRouter(prefix="/follows", tags=["follows"])

FREE_TIER_FOLLOW_LIMIT = 3


class FollowCreate(BaseModel):
    narrative_event_id: uuid.UUID
    follow_keywords: list[str] = []


@router.get("/")
async def list_follows(db: DbDep, user: UserDep) -> dict:
    result = await db.execute(
        select(UserFollow)
        .where(UserFollow.user_id == user.id)
        .where(UserFollow.is_active == True)
    )
    follows = result.scalars().all()

    items = []
    for follow in follows:
        event = await db.get(NarrativeEvent, follow.narrative_event_id)
        items.append(
            {
                "id": str(follow.id),
                "narrative_event_id": str(follow.narrative_event_id),
                "event_title": event.canonical_title if event else None,
                "event_status": event.current_status if event else None,
                "follow_keywords": follow.follow_keywords,
                "created_at": follow.created_at.isoformat(),
            }
        )

    return {"follows": items}


@router.post("/")
async def create_follow(body: FollowCreate, db: DbDep, user: UserDep) -> dict:
    # Free tier: max 3 follows
    if user.tier == "free":
        count_result = await db.execute(
            select(UserFollow)
            .where(UserFollow.user_id == user.id)
            .where(UserFollow.is_active == True)
        )
        count = len(count_result.scalars().all())
        if count >= FREE_TIER_FOLLOW_LIMIT:
            raise HTTPException(status_code=402, detail="Free tier limited to 3 follows")

    event = await db.get(NarrativeEvent, body.narrative_event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Check if already following
    existing = await db.execute(
        select(UserFollow)
        .where(UserFollow.user_id == user.id)
        .where(UserFollow.narrative_event_id == body.narrative_event_id)
        .where(UserFollow.is_active == True)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already following this event")

    follow = UserFollow(
        id=uuid.uuid4(),
        user_id=user.id,
        narrative_event_id=body.narrative_event_id,
        follow_keywords=body.follow_keywords or event.follow_keywords or [],
        created_at=datetime.now(timezone.utc),
    )
    db.add(follow)
    await db.flush()
    await db.commit()

    return {
        "id": str(follow.id),
        "narrative_event_id": str(follow.narrative_event_id),
        "event_title": event.canonical_title,
        "follow_keywords": follow.follow_keywords,
        "created_at": follow.created_at.isoformat(),
    }


@router.delete("/{follow_id}")
async def delete_follow(follow_id: uuid.UUID, db: DbDep, user: UserDep) -> dict:
    follow = await db.get(UserFollow, follow_id)
    if not follow or follow.user_id != user.id:
        raise HTTPException(status_code=404, detail="Follow not found")

    follow.is_active = False
    db.add(follow)
    await db.commit()

    return {"deleted": True}
