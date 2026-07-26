"""
Organizations — the tenant a site register, its people and its alerts belong to.

Before this, ``user_id`` was the only scoping key in the backend, which made a shared
register impossible: a GSOC is a team reading one asset list, not a set of individuals
each following their own events. This adds the tenant and the membership that carries
a person's role inside it.

Deliberately flat: no parent_id, no nesting. The incumbent offers "Wipro and
Sub-Organizations", but nesting multiplies the cost of every permission check and
every roll-up, and no customer requirement for it has been observed. It can be added
when one is; it cannot easily be removed once every query assumes it.

Roles are ``admin`` (manages members) · ``analyst`` (edits the register) · ``viewer``
(reads). Role lives on the membership row and NOT on ``User.tier``, which is billing.
"""

import re
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from backend.api.dependencies import DbDep, OrgDep, UserDep
from backend.models.organization import OrgMember, Organization
from backend.models.user import User

router = APIRouter(prefix="/org", tags=["org"])

ROLES = {"admin", "analyst", "viewer"}


class OrgCreate(BaseModel):
    name: str
    slug: str | None = None


class MemberAdd(BaseModel):
    email: str
    role: str = "viewer"


class MemberUpdate(BaseModel):
    role: str


def _slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return s or "org"


def _require_admin(org: OrgMember) -> None:
    if org.role != "admin":
        raise HTTPException(status_code=403, detail="Only an organization admin can do this")


@router.get("")
async def current_org(db: DbDep, org: OrgDep) -> dict:
    organization = await db.get(Organization, org.org_id)
    members = (await db.execute(
        select(func.count()).select_from(OrgMember)
        .where(OrgMember.org_id == org.org_id)
        .where(OrgMember.is_active == True)  # noqa: E712 — repo idiom
    )).scalar_one()

    return {
        "id": str(org.org_id),
        "name": organization.name if organization else None,
        "slug": organization.slug if organization else None,
        "role": org.role,
        "member_count": members,
    }


@router.post("")
async def create_org(body: OrgCreate, db: DbDep, user: UserDep) -> dict:
    """Create an organization and make the caller its admin.

    Uses UserDep rather than OrgDep — this is how the FIRST org comes into existence,
    so it cannot require one to already exist. A user who is already a member of one
    is refused: joining a second tenant is an invitation, not a self-service action,
    and silently allowing it would put the account into the ambiguous multi-membership
    state that ``get_membership`` then has to reject on every subsequent request.
    """
    existing = (await db.execute(
        select(OrgMember).where(OrgMember.user_id == user.id).where(OrgMember.is_active == True)  # noqa: E712
    )).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="This account already belongs to an organization")

    slug = _slugify(body.slug or body.name)
    taken = (await db.execute(select(Organization).where(Organization.slug == slug))).scalars().first()
    if taken:
        raise HTTPException(status_code=409, detail=f'The slug "{slug}" is taken')

    organization = Organization(id=uuid.uuid4(), name=body.name, slug=slug, is_active=True)
    db.add(organization)
    await db.flush()

    membership = OrgMember(
        id=uuid.uuid4(), org_id=organization.id, user_id=user.id, role="admin", is_active=True,
    )
    db.add(membership)
    await db.commit()

    return {"id": str(organization.id), "name": organization.name,
            "slug": organization.slug, "role": "admin", "member_count": 1}


@router.get("/members")
async def list_members(db: DbDep, org: OrgDep) -> dict:
    rows = (await db.execute(
        select(OrgMember, User)
        .join(User, User.id == OrgMember.user_id)
        .where(OrgMember.org_id == org.org_id)
        .where(OrgMember.is_active == True)  # noqa: E712
        .order_by(User.email)
    )).all()

    return {"members": [{
        "id": str(m.id),
        "user_id": str(m.user_id),
        "email": u.email,
        "role": m.role,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    } for m, u in rows]}


@router.post("/members")
async def add_member(body: MemberAdd, db: DbDep, org: OrgDep) -> dict:
    """Add an existing account to this organization.

    There is no invitation email yet, so this deliberately only works for an account
    that already exists. Returning 404 for an unknown address is the honest answer:
    pretending to have invited someone we cannot reach would be worse than refusing.
    """
    _require_admin(org)
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(ROLES)}")

    email = body.email.strip().lower()
    user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="No account with that email address")

    existing = (await db.execute(
        select(OrgMember).where(OrgMember.org_id == org.org_id).where(OrgMember.user_id == user.id)
    )).scalars().first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=409, detail="Already a member of this organization")
        # Re-activate rather than insert: the UNIQUE (org_id, user_id) constraint would
        # reject a second row, and reusing the old one keeps their join date honest.
        existing.is_active = True
        existing.role = body.role
        db.add(existing)
        await db.commit()
        return {"id": str(existing.id), "user_id": str(user.id),
                "email": user.email, "role": existing.role}

    membership = OrgMember(
        id=uuid.uuid4(), org_id=org.org_id, user_id=user.id, role=body.role, is_active=True,
    )
    db.add(membership)
    await db.commit()
    return {"id": str(membership.id), "user_id": str(user.id),
            "email": user.email, "role": membership.role}


@router.patch("/members/{member_id}")
async def update_member(member_id: uuid.UUID, body: MemberUpdate, db: DbDep, org: OrgDep) -> dict:
    _require_admin(org)
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(ROLES)}")

    member = await db.get(OrgMember, member_id)
    if not member or member.org_id != org.org_id or not member.is_active:
        raise HTTPException(status_code=404, detail="Member not found")

    # An organization that loses its last admin cannot be administered again without
    # us reaching into the database, so demoting the final one is refused here.
    if member.role == "admin" and body.role != "admin":
        admins = (await db.execute(
            select(func.count()).select_from(OrgMember)
            .where(OrgMember.org_id == org.org_id)
            .where(OrgMember.role == "admin")
            .where(OrgMember.is_active == True)  # noqa: E712
        )).scalar_one()
        if admins <= 1:
            raise HTTPException(status_code=409, detail="An organization must keep at least one admin")

    member.role = body.role
    db.add(member)
    await db.commit()
    return {"id": str(member.id), "user_id": str(member.user_id), "role": member.role}


@router.delete("/members/{member_id}")
async def remove_member(member_id: uuid.UUID, db: DbDep, org: OrgDep) -> dict:
    _require_admin(org)

    member = await db.get(OrgMember, member_id)
    if not member or member.org_id != org.org_id or not member.is_active:
        raise HTTPException(status_code=404, detail="Member not found")

    if member.role == "admin":
        admins = (await db.execute(
            select(func.count()).select_from(OrgMember)
            .where(OrgMember.org_id == org.org_id)
            .where(OrgMember.role == "admin")
            .where(OrgMember.is_active == True)  # noqa: E712
        )).scalar_one()
        if admins <= 1:
            raise HTTPException(status_code=409, detail="An organization must keep at least one admin")

    member.is_active = False
    db.add(member)
    await db.commit()
    return {"deleted": True, "id": str(member_id)}
