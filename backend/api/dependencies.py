import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Header, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.models.organization import OrgMember
from backend.models.user import User

settings = get_settings()

# Roles that may WRITE inside an organization. A viewer is a real, useful role — a
# GSOC has watch-floor staff who must never be able to edit the site register that
# every alert is scored against.
ORG_WRITER_ROLES = {"admin", "analyst"}


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        # Bearer tokens are minted by backend/api/routes/auth.py (_issue_token),
        # HS256-signed with secret_key — so verification MUST use the same key.
        # (Supabase tokens are handled separately by /auth/exchange via the Supabase
        # SDK and are never presented as bearer tokens here, so the former
        # `supabase_service_key or …` fallback only broke logins when that key was set.)
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.tier != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


async def get_membership(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    x_org_id: Annotated[str | None, Header()] = None,
) -> OrgMember:
    """Resolve which organization the caller is acting in, and as what.

    Returns the MEMBERSHIP row rather than the Organization, because every caller
    needs both halves: ``org_id`` to scope the query and ``role`` to decide whether
    the write is allowed. Handing back only the org would force each route to
    re-query for the role, which is how one route eventually forgets.

    Scoping is a dependency, not a ``where`` clause copied into every handler.
    That matters more here than for follows: a leaked ``org_id`` filter does not
    show a user their own stale data, it shows them another company's site register.

    Multiple memberships are resolved by an explicit ``X-Org-Id`` header. If a user
    belongs to several organizations and does not say which, this raises rather than
    silently picking one — quietly defaulting would show them a real register that
    is simply not the one they asked about, and nothing on screen would say so.
    """
    stmt = (
        select(OrgMember)
        .where(OrgMember.user_id == current_user.id)
        .where(OrgMember.is_active == True)  # noqa: E712 — repo idiom
    )
    if x_org_id:
        try:
            stmt = stmt.where(OrgMember.org_id == uuid.UUID(x_org_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="X-Org-Id is not a valid id")

    memberships = (await db.execute(stmt)).scalars().all()

    if not memberships:
        # 403, not 404: the caller is authenticated, they simply are not a member of
        # this organization (or of any). 404 would leak nothing either, but 403 is
        # the honest description and keeps 404 meaning "this row does not exist".
        raise HTTPException(status_code=403, detail="No organization for this account")
    if len(memberships) > 1:
        raise HTTPException(
            status_code=400,
            detail="This account belongs to several organizations — set the X-Org-Id header.",
        )
    return memberships[0]


async def require_org_writer(
    membership: Annotated[OrgMember, Depends(get_membership)],
) -> OrgMember:
    if membership.role not in ORG_WRITER_ROLES:
        raise HTTPException(
            status_code=403, detail="Your role is read-only in this organization"
        )
    return membership


DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]
AdminDep = Annotated[User, Depends(require_admin)]
# The membership the caller is acting under: carries org_id (scope) and role (permission).
OrgDep = Annotated[OrgMember, Depends(get_membership)]
OrgWriterDep = Annotated[OrgMember, Depends(require_org_writer)]
