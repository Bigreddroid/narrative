"""
Advisories — the advice library, read-only by design.

There is no POST here and there never should be. Every sheet is published by a named
government; the only writer is ``advisory_worker``. An endpoint that let us add our
own guidance would turn an ingest into an authoring surface, and the moment a sheet
carried our words instead of a government's, the citation under it would be a lie.

Each response carries the issuing authority, that authority's own level vocabulary,
its publication date and a link to the original — everything a reader needs to check
us. ``/for-register`` answers the question a security team actually asks: what does
official advice say about the places we have people.
"""

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from backend.api.dependencies import DbDep, OrgDep, UserDep
from backend.countries import to_iso2
from backend.feeds.advisories import AUTHORITY_LABELS
from backend.models.advisory import Advisory
from backend.models.person import Trip
from backend.models.site import Site
from backend.services import source_reliability

router = APIRouter(prefix="/advisories", tags=["advisories"])


def _serialize(a: Advisory, full: bool = False) -> dict:
    out = {
        "id": str(a.id),
        "authority": a.authority,
        "authority_label": AUTHORITY_LABELS.get(a.authority, a.authority),
        "country": a.country,
        "country_iso": a.country_iso,
        # The issuer's own words for its own scale. Never converted, never averaged
        # with another government's — see backend/models/advisory.py.
        "level_code": a.level_code,
        "level_label": a.level_label,
        "summary": a.summary,
        "url": a.url,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "fetched_at": a.fetched_at.isoformat() if a.fetched_at else None,
        # Graded through the same Admiralty path as any other source, not by a special
        # case: source_reliability's provenance prior maps the `gov_` prefix to B.
        "grade": source_reliability.grade(a.authority, corroboration_count=1)["grade"],
    }
    if full:
        out["sections"] = a.sections or {}
    return out


@router.get("")
async def list_advisories(
    db: DbDep,
    user: UserDep,
    country: str | None = Query(None, description="Country name or ISO-3166 alpha-2 code"),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    stmt = select(Advisory).where(Advisory.is_current == True)  # noqa: E712 — repo idiom
    if country:
        iso = to_iso2(country)
        stmt = (stmt.where(Advisory.country_iso == iso) if iso
                else stmt.where(Advisory.country.ilike(country)))

    rows = (await db.execute(
        stmt.order_by(Advisory.country, Advisory.authority).limit(limit)
    )).scalars().all()

    return {
        "advisories": [_serialize(a) for a in rows],
        "count": len(rows),
        # Named up front. A library that silently holds one authority's view looks
        # identical to one holding two, and the difference matters to a reader
        # deciding how much weight to put on it.
        "authorities": sorted({a.authority for a in rows}),
    }


@router.get("/for-register")
async def advisories_for_register(db: DbDep, org: OrgDep) -> dict:
    """Official advice for every country this organization has people or property in.

    Countries with no sheet are LISTED, not omitted. "We hold no advisory for Malta"
    is a different statement from Malta not appearing at all, and only one of them is
    honest about a gap in the library.
    """
    site_countries = (await db.execute(
        select(Site.country).where(Site.org_id == org.org_id)
        .where(Site.is_active == True).where(Site.country.isnot(None))  # noqa: E712
    )).scalars().all()
    trip_countries = (await db.execute(
        select(Trip.to_country).where(Trip.org_id == org.org_id)
        .where(Trip.is_active == True).where(Trip.to_country.isnot(None))  # noqa: E712
    )).scalars().all()

    wanted, seen = [], set()
    for c in list(site_countries) + list(trip_countries):
        key = (c or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            wanted.append(c.strip())

    if not wanted:
        return {"countries": [], "covered": 0, "uncovered": 0,
                "note": "No countries in your register yet."}

    isos = {c: to_iso2(c) for c in wanted}
    rows = (await db.execute(
        select(Advisory).where(Advisory.is_current == True)  # noqa: E712
        .where(Advisory.country_iso.in_([i for i in isos.values() if i]))
    )).scalars().all()

    by_iso: dict[str, list] = {}
    for a in rows:
        by_iso.setdefault(a.country_iso, []).append(a)

    out = []
    for c in sorted(wanted):
        found = by_iso.get(isos[c], [])
        out.append({
            "country": c,
            "country_iso": isos[c],
            "advisories": [_serialize(a) for a in found],
            "covered": bool(found),
        })
    covered = sum(1 for x in out if x["covered"])
    return {"countries": out, "covered": covered, "uncovered": len(out) - covered}


@router.get("/{advisory_id}")
async def get_advisory(advisory_id: uuid.UUID, db: DbDep, user: UserDep) -> dict:
    a = await db.get(Advisory, advisory_id)
    if not a:
        raise HTTPException(status_code=404, detail="Advisory not found")
    # Superseded sheets are readable by id on purpose: the history is the point, and a
    # link taken from an old briefing must not 404 just because the sheet moved on.
    return {**_serialize(a, full=True), "is_current": a.is_current}
