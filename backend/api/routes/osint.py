"""
OSINT enrichment + triage-flywheel endpoints.

The heavy 1,098-tool catalog and the entity-investigate templating were removed in
the Phase-1 refocus (they were mostly a static manifest the frontend rendered). What
remains is the part that does real work server-side: keyless live enrichment on
concrete entities (ip/domain/cve/hash/crypto) and the triage-flywheel stats.
"""

import ipaddress
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.api.dependencies import DbDep, UserDep
from backend.models.osint_triage_decision import OsintTriageDecision
from backend.services import osint_enrich

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/osint", tags=["osint"])

_VALID_KINDS = {
    "username", "domain", "ip", "email", "name", "location", "phone", "image",
    # entity kinds for the enrichable categories (blockchain, malware, CVE, transport):
    "crypto", "hash", "cve", "vehicle", "media",
}


def detect_entity_kind(value: str) -> str:
    """Best-effort classification of a raw entity value → an enrichment kind.
    Used when the caller doesn't pass an explicit ?kind=."""
    v = (value or "").strip()
    if not v:
        return "name"
    if "@" in v and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
        return "email"
    try:
        ipaddress.ip_address(v)
        return "ip"
    except ValueError:
        pass
    if re.fullmatch(r"-?\d{1,3}\.\d+\s*,\s*-?\d{1,3}\.\d+", v):
        return "location"
    if re.fullmatch(r"CVE-\d{4}-\d{4,}", v, re.I):
        return "cve"
    # crypto: ETH address/tx (0x + 40/64 hex), BTC bech32 (bc1…), BTC legacy (1/3…).
    if (re.fullmatch(r"0x(?:[0-9a-f]{40}|[0-9a-f]{64})", v, re.I)
            or re.fullmatch(r"bc1[a-z0-9]{20,87}", v, re.I)
            or re.fullmatch(r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}", v)):
        return "crypto"
    # file hash: md5(32) / sha1(40) / sha256(64) hex — checked before username so a
    # bare hex blob doesn't read as a handle.
    if re.fullmatch(r"[0-9a-f]{32}|[0-9a-f]{40}|[0-9a-f]{64}", v, re.I):
        return "hash"
    if re.fullmatch(r"IMO\s?\d{7}", v, re.I):
        return "vehicle"
    if " " not in v and re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", v, re.I):
        return "domain"
    if " " not in v and re.fullmatch(r"[a-z0-9_.-]+", v, re.I):
        return "username"
    return "name"


@router.get("/enrich")
async def enrich(user: UserDep, value: str, kind: str | None = None) -> dict:
    """Tier 1 live enrichment: real facts fetched server-side from keyless APIs
    (ip/domain/cve/hash/crypto). Paid feature; free tier and non-enrichable kinds get
    an empty `facts` set."""
    value = (value or "").strip()
    if user.tier == "free" or not value:
        return {"value": value, "kind": kind, "facts": [], "sources": [],
                "limited": user.tier == "free"}

    resolved = (kind or "").strip().lower()
    if resolved not in _VALID_KINDS:
        resolved = detect_entity_kind(value)

    return await osint_enrich.enrich(value, resolved)


@router.get("/triage/stats")
async def triage_stats(user: UserDep, db: DbDep, hours: int = 24) -> dict:
    """The OSINT triage flywheel, made visible: over the last `hours`, how many
    open-source posts the agent KEPT vs DROPPED, broken down by reason and by source.

    Drops normally vanish (triage returns None), so this is the only window into the
    rejection funnel — what the thresholds are actually filtering out, and whether
    they're too tight. Paid feature; free tier gets an empty (gated) summary. If the
    decisions table isn't present yet (migration drift), degrade to an empty summary
    rather than 500."""
    hours = max(1, min(int(hours or 24), 168))
    empty = {"window_hours": hours, "kept": 0, "dropped": 0, "keep_rate": None,
             "by_reason": [], "by_source": []}
    if user.tier == "free":
        return {**empty, "limited": True}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        totals = (await db.execute(
            select(OsintTriageDecision.kept, func.count())
            .where(OsintTriageDecision.created_at >= cutoff)
            .group_by(OsintTriageDecision.kept)
        )).all()
        reasons = (await db.execute(
            select(OsintTriageDecision.reason, OsintTriageDecision.kept, func.count())
            .where(OsintTriageDecision.created_at >= cutoff)
            .group_by(OsintTriageDecision.reason, OsintTriageDecision.kept)
            .order_by(func.count().desc())
        )).all()
        sources = (await db.execute(
            select(OsintTriageDecision.source, func.count())
            .where(OsintTriageDecision.created_at >= cutoff)
            .group_by(OsintTriageDecision.source)
            .order_by(func.count().desc())
        )).all()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.warning("triage_stats query failed (table missing?): %s", exc)
        return {**empty, "limited": False, "unavailable": True}

    kept = sum(c for k, c in totals if k)
    dropped = sum(c for k, c in totals if not k)
    total = kept + dropped
    return {
        "window_hours": hours,
        "kept": kept,
        "dropped": dropped,
        "keep_rate": round(kept / total, 3) if total else None,
        "by_reason": [{"reason": r, "kept": bool(k), "count": c} for r, k, c in reasons],
        "by_source": [{"source": s, "count": c} for s, c in sources],
        "limited": False,
    }
