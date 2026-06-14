from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.dependencies import DbDep, UserDep

router = APIRouter(prefix="/users", tags=["users"])


class UserProfileUpdate(BaseModel):
    city: str | None = None
    country: str | None = None
    profession: str | None = None
    spending_categories: list[str] | None = None
    fcm_token: str | None = None
    notification_preferences: dict | None = None


@router.get("/me")
async def get_me(user: UserDep) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "city": user.city,
        "country": user.country,
        "profession": user.profession,
        "spending_categories": user.spending_categories,
        "tier": user.tier,
        "notification_preferences": user.notification_preferences,
        "created_at": user.created_at.isoformat(),
    }


@router.patch("/me")
async def update_me(body: UserProfileUpdate, db: DbDep, user: UserDep) -> dict:
    if body.city is not None:
        user.city = body.city
    if body.country is not None:
        user.country = body.country
    if body.profession is not None:
        user.profession = body.profession
    if body.spending_categories is not None:
        user.spending_categories = body.spending_categories
    if body.fcm_token is not None:
        user.fcm_token = body.fcm_token
    if body.notification_preferences is not None:
        user.notification_preferences = body.notification_preferences

    db.add(user)
    await db.commit()

    return {"updated": True}
