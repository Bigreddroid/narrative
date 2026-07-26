"""
Subscriptions, distribution lists, and the delivery log.

This is what makes the Settings page honest. ``web/src/pages/Settings.jsx`` has shown
users a toggle called "email digest — periodic summary of high-impact consequences"
that writes to ``users.notification_preferences``, a JSONB column **no backend code
has ever read**. The control looked like a feature and was a decoration. These routes
give it something real to write to.

``GET /subscriptions/deliveries`` exists for the same reason the benchmark ledger is
public: a customer should be able to check what we actually sent them, including what
we suppressed and why, rather than take our word for it.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.dependencies import DbDep, OrgDep, OrgWriterDep, UserDep
from backend.models.delivery import (
    AlertSubscription, Delivery, DistributionList, DistributionMember,
)
from backend.models.site import Site
from backend.services import mailer

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

CHANNELS = {"email", "push"}
SCOPES = {"org", "site", "country"}
CADENCES = {"daily", "weekly"}
SEVERITIES = {"minimal", "low", "moderate", "high", "extreme"}


class SubscriptionCreate(BaseModel):
    channel: str = "email"
    scope: str = "org"
    scope_ref: str | None = None
    min_severity: str = "high"
    cadence: str = "daily"
    list_id: uuid.UUID | None = None


class ListCreate(BaseModel):
    name: str


class MemberAdd(BaseModel):
    email: str
    name: str | None = None


def _serialize_sub(s: AlertSubscription) -> dict:
    return {
        "id": str(s.id), "channel": s.channel, "scope": s.scope, "scope_ref": s.scope_ref,
        "min_severity": s.min_severity, "cadence": s.cadence,
        "user_id": str(s.user_id) if s.user_id else None,
        "list_id": str(s.list_id) if s.list_id else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("")
async def list_subscriptions(db: DbDep, org: OrgDep) -> dict:
    subs = (await db.execute(
        select(AlertSubscription)
        .where(AlertSubscription.org_id == org.org_id)
        .where(AlertSubscription.is_active == True)  # noqa: E712 — repo idiom
        .order_by(AlertSubscription.created_at)
    )).scalars().all()

    # The posture is returned WITH the subscriptions, never separately. A page that
    # lists live subscriptions without saying sending is switched off is the same
    # class of lie the Settings toggle already was.
    refusal = mailer.preflight()
    return {
        "subscriptions": [_serialize_sub(s) for s in subs],
        "sending_enabled": refusal is None,
        "sending_status": "Sending is live" if refusal is None else refusal.error,
    }


@router.post("")
async def create_subscription(body: SubscriptionCreate, db: DbDep, user: UserDep,
                              org: OrgDep) -> dict:
    if body.channel not in CHANNELS:
        raise HTTPException(status_code=400, detail=f"channel must be one of {sorted(CHANNELS)}")
    if body.scope not in SCOPES:
        raise HTTPException(status_code=400, detail=f"scope must be one of {sorted(SCOPES)}")
    if body.cadence not in CADENCES:
        raise HTTPException(status_code=400, detail=f"cadence must be one of {sorted(CADENCES)}")
    if body.min_severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail=f"min_severity must be one of {sorted(SEVERITIES)}")
    if body.scope in {"site", "country"} and not body.scope_ref:
        raise HTTPException(status_code=400, detail=f"scope '{body.scope}' needs a scope_ref")

    # A site-scoped subscription pointed at someone else's site would leak that org's
    # events into this org's inbox. Ownership is checked, not assumed.
    if body.scope == "site":
        try:
            site = await db.get(Site, uuid.UUID(body.scope_ref))
        except ValueError:
            raise HTTPException(status_code=400, detail="scope_ref must be a site id")
        if not site or site.org_id != org.org_id:
            raise HTTPException(status_code=404, detail="Site not found")

    # Subscribing a LIST is an act on behalf of other people, so it needs write rights;
    # subscribing yourself does not.
    if body.list_id is not None:
        if org.role not in {"admin", "analyst"}:
            raise HTTPException(status_code=403, detail="Your role cannot subscribe a distribution list")
        dl = await db.get(DistributionList, body.list_id)
        if not dl or dl.org_id != org.org_id:
            raise HTTPException(status_code=404, detail="Distribution list not found")

    sub = AlertSubscription(
        id=uuid.uuid4(), org_id=org.org_id,
        user_id=None if body.list_id else user.id,
        list_id=body.list_id,
        channel=body.channel, scope=body.scope, scope_ref=body.scope_ref,
        min_severity=body.min_severity, cadence=body.cadence, is_active=True,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return _serialize_sub(sub)


@router.delete("/{subscription_id}")
async def delete_subscription(subscription_id: uuid.UUID, db: DbDep, user: UserDep,
                              org: OrgDep) -> dict:
    sub = await db.get(AlertSubscription, subscription_id)
    if not sub or sub.org_id != org.org_id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    # Anyone may unsubscribe themselves; only a writer may unsubscribe a shared list.
    if sub.list_id is not None and org.role not in {"admin", "analyst"}:
        raise HTTPException(status_code=403, detail="Your role cannot change a shared subscription")
    if sub.user_id is not None and sub.user_id != user.id and org.role != "admin":
        raise HTTPException(status_code=403, detail="That subscription belongs to someone else")

    sub.is_active = False
    db.add(sub)
    await db.commit()
    return {"deleted": True, "id": str(subscription_id)}


# ── distribution lists ───────────────────────────────────────────────────────

@router.get("/lists")
async def list_lists(db: DbDep, org: OrgDep) -> dict:
    lists = (await db.execute(
        select(DistributionList)
        .where(DistributionList.org_id == org.org_id)
        .where(DistributionList.is_active == True)  # noqa: E712
        .order_by(DistributionList.name)
    )).scalars().all()

    out = []
    for dl in lists:
        members = (await db.execute(
            select(DistributionMember)
            .where(DistributionMember.list_id == dl.id)
            .where(DistributionMember.is_active == True)  # noqa: E712
        )).scalars().all()
        out.append({
            "id": str(dl.id), "name": dl.name,
            "members": [{"id": str(m.id), "email": m.email, "name": m.name,
                         "unsubscribed": m.unsubscribed_at is not None} for m in members],
            # Counted excluding unsubscribes, because that is the number that will
            # actually be mailed — reporting the raw membership would overstate reach.
            "reachable": sum(1 for m in members if m.unsubscribed_at is None),
        })
    return {"lists": out}


@router.post("/lists")
async def create_list(body: ListCreate, db: DbDep, org: OrgWriterDep) -> dict:
    existing = (await db.execute(
        select(DistributionList)
        .where(DistributionList.org_id == org.org_id)
        .where(DistributionList.name == body.name)
    )).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="A list with that name already exists")

    dl = DistributionList(id=uuid.uuid4(), org_id=org.org_id, name=body.name, is_active=True)
    db.add(dl)
    await db.commit()
    return {"id": str(dl.id), "name": dl.name, "members": [], "reachable": 0}


@router.post("/lists/{list_id}/members")
async def add_member(list_id: uuid.UUID, body: MemberAdd, db: DbDep, org: OrgWriterDep) -> dict:
    dl = await db.get(DistributionList, list_id)
    if not dl or dl.org_id != org.org_id:
        raise HTTPException(status_code=404, detail="Distribution list not found")

    email = body.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=400, detail="That is not an email address")

    existing = (await db.execute(
        select(DistributionMember)
        .where(DistributionMember.list_id == list_id)
        .where(DistributionMember.email == email)
    )).scalars().first()
    if existing:
        if existing.unsubscribed_at is not None:
            # 🔴 Re-adding does NOT resubscribe. Someone who opted out stays opted out
            # until they say otherwise; an admin re-uploading a roster must not be able
            # to overturn a person's decision to stop receiving mail.
            raise HTTPException(
                status_code=409,
                detail="That address unsubscribed and cannot be re-added from here.",
            )
        raise HTTPException(status_code=409, detail="Already on this list")

    m = DistributionMember(id=uuid.uuid4(), list_id=list_id, email=email,
                           name=body.name, is_active=True)
    db.add(m)
    await db.commit()
    return {"id": str(m.id), "email": m.email, "name": m.name, "unsubscribed": False}


@router.delete("/lists/{list_id}/members/{member_id}")
async def remove_member(list_id: uuid.UUID, member_id: uuid.UUID, db: DbDep,
                        org: OrgWriterDep) -> dict:
    dl = await db.get(DistributionList, list_id)
    if not dl or dl.org_id != org.org_id:
        raise HTTPException(status_code=404, detail="Distribution list not found")
    m = await db.get(DistributionMember, member_id)
    if not m or m.list_id != list_id:
        raise HTTPException(status_code=404, detail="Member not found")

    m.is_active = False
    db.add(m)
    await db.commit()
    return {"deleted": True, "id": str(member_id)}


# ── the log ──────────────────────────────────────────────────────────────────

@router.get("/deliveries")
async def list_deliveries(db: DbDep, org: OrgDep, limit: int = Query(50, ge=1, le=200)) -> dict:
    rows = (await db.execute(
        select(Delivery).where(Delivery.org_id == org.org_id)
        .order_by(Delivery.queued_at.desc()).limit(limit)
    )).scalars().all()

    return {"deliveries": [{
        "id": str(d.id),
        "recipient": d.recipient,
        "subject": d.subject,
        "item_count": d.item_count,
        # suppressed is reported as itself, never folded into sent or failed: one is
        # our decision, the other is a fault, and the customer is entitled to know
        # which of the two kept a message from arriving.
        "status": d.status,
        "error": d.error,
        "queued_at": d.queued_at.isoformat() if d.queued_at else None,
        "sent_at": d.sent_at.isoformat() if d.sent_at else None,
    } for d in rows], "count": len(rows)}
