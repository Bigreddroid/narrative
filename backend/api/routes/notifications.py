from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.dependencies import DbDep, UserDep
from backend.models.user import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


class PushTokenBody(BaseModel):
    fcm_token: str
    platform: str = "unknown"


@router.post("/register")
async def register_push_token(body: PushTokenBody, db: DbDep, user: UserDep) -> dict:
    """Store the Expo/FCM push token for the current user."""
    user.fcm_token = body.fcm_token
    db.add(user)
    await db.commit()
    return {"registered": True}


@router.get("/")
async def list_notifications(db: DbDep, user: UserDep) -> dict:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.sent_at.desc())
        .limit(50)
    )
    notifications = result.scalars().all()

    return {
        "notifications": [
            {
                "id": str(n.id),
                "narrative_event_id": str(n.narrative_event_id) if n.narrative_event_id else None,
                "type": n.type,
                "payload": n.payload,
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                "opened_at": n.opened_at.isoformat() if n.opened_at else None,
            }
            for n in notifications
        ]
    }


@router.post("/{notification_id}/open")
async def mark_opened(notification_id, db: DbDep, user: UserDep) -> dict:
    import uuid as _uuid
    notification = await db.get(Notification, _uuid.UUID(str(notification_id)))
    if not notification or notification.user_id != user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.opened_at = datetime.now(timezone.utc)
    db.add(notification)
    await db.commit()

    return {"opened": True}
