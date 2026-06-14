import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from jose import jwt
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.dependencies import DbDep
from backend.config import get_settings
from backend.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class DevLoginRequest(BaseModel):
    email: str
    password: str  # ignored — any value accepted in dev


@router.post("/dev-login")
async def dev_login(body: DevLoginRequest, db: DbDep) -> dict:
    """
    Dev-only endpoint. Disabled in production.
    Find or create user by email and return a signed JWT.
    """
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")

    email = body.email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=uuid.uuid4(),
            email=email,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()
        await db.commit()

    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")

    return {
        "access_token": token,
        "is_new_user": user.city is None,
    }


class SupabaseTokenExchange(BaseModel):
    supabase_access_token: str
    email: str


@router.post("/exchange")
async def exchange_token(body: SupabaseTokenExchange, db: DbDep) -> dict:
    """
    Exchange a Supabase JWT for a user record.
    Creates user if first login.
    Returns user profile for client to store.
    """
    # Verify the Supabase token
    try:
        from supabase import create_client
        supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
        supabase_user = supabase.auth.get_user(body.supabase_access_token)
        if not supabase_user or not supabase_user.user:
            raise HTTPException(status_code=401, detail="Invalid Supabase token")
        supabase_uid = supabase_user.user.id
        email = supabase_user.user.email or body.email
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {exc}")

    # Find or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Use Supabase UUID as our user ID for consistency
        try:
            user_id = uuid.UUID(supabase_uid)
        except Exception:
            user_id = uuid.uuid4()

        user = User(
            id=user_id,
            email=email,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()
        await db.commit()

    return {
        "user_id": str(user.id),
        "email": user.email,
        "tier": user.tier,
        "is_new_user": user.city is None,
    }
