import hashlib
import secrets
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

PBKDF2_ITERS = 200_000


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, PBKDF2_ITERS)
    return f"pbkdf2_sha256${PBKDF2_ITERS}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _algo, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), int(iters))
        return secrets.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def _issue_token(user: User) -> dict:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return {"access_token": token, "is_new_user": user.city is None}


class DevLoginRequest(BaseModel):
    email: str
    password: str  # ignored — any value accepted in dev


# Dev test accounts → tier (mirrors web/src/lib/tiers.js DEV_ACCOUNTS).
_DEV_TIERS = {
    "free@narrative.dev": "free",
    "pro@narrative.dev": "pro",
    "intel@narrative.dev": "intelligence",
    "enterprise@narrative.dev": "enterprise",
    "admin@narrative.dev": "admin",
}

# Beta-test accounts: real, password-protected accounts that ALSO work in
# production (unlike /dev-login, which is disabled when APP_ENV=production).
# Beta testers sign in through the normal /login flow with these credentials,
# and the account is auto-provisioned at the given tier on first login.
_BETA_ACCOUNTS = {
    "enterprise@narrative.dev": {"password": "betatest1", "tier": "enterprise"},
}


async def _provision_beta_account(email: str, password: str, db, beta: dict) -> User | None:
    """Find-or-create a beta account and pin its tier. None if password wrong."""
    if password != beta["password"]:
        return None
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user:
        user = User(
            id=uuid.uuid4(),
            email=email,
            tier=beta["tier"],
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()
    elif user.tier != beta["tier"]:
        user.tier = beta["tier"]
    await db.commit()
    return user


@router.post("/dev-login")
async def dev_login(body: DevLoginRequest, db: DbDep) -> dict:
    """
    Dev-only endpoint. Disabled in production.
    Find or create user by email and return a signed JWT.
    """
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")

    email = body.email.strip().lower()
    beta = _BETA_ACCOUNTS.get(email)
    if beta is not None and body.password != beta["password"]:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=uuid.uuid4(),
            email=email,
            tier=_DEV_TIERS.get(email, "free"),
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()
        await db.commit()
    elif email in _DEV_TIERS and user.tier != _DEV_TIERS[email]:
        # Keep dev accounts on their named tier (no manual DB edits needed).
        user.tier = _DEV_TIERS[email]
        await db.commit()

    return _issue_token(user)


class CredentialsRequest(BaseModel):
    email: str
    password: str


@router.post("/signup")
async def signup(body: CredentialsRequest, db: DbDep) -> dict:
    """Real email+password signup. Works in production. Returns a signed JWT."""
    email = body.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing and existing.password_hash:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    if existing:  # dev/Supabase-created shell with no password yet — claim it
        existing.password_hash = hash_password(body.password)
        user = existing
    else:
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=hash_password(body.password),
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
    await db.flush()
    await db.commit()
    return _issue_token(user)


@router.post("/login")
async def login(body: CredentialsRequest, db: DbDep) -> dict:
    """Real email+password login. Works in production. Returns a signed JWT."""
    email = body.email.strip().lower()

    # Beta-test accounts (e.g. enterprise@narrative.dev) are provisioned on
    # demand so they work on the deployed build, where /dev-login is disabled.
    beta = _BETA_ACCOUNTS.get(email)
    if beta is not None:
        user = await _provision_beta_account(email, body.password, db, beta)
        if user is None:
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        return _issue_token(user)

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return _issue_token(user)


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
