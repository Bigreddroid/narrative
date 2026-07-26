"""
Sites — the customer's site register, and the join key of the whole product.

Until this route existed the executive deck computed every per-site number in the
browser from a 214-row JavaScript fixture. Nothing a customer uploaded could reach
it, because there was nowhere to put it. This is that place.

Three things happen here that are worth stating plainly:

1. **Import is idempotent.** Re-uploading the same file changes nothing. A register
   is re-sent whenever HR or facilities regenerates it, and an importer that appends
   would double every headcount figure on the board within a week.

2. **Import audits, it does not reject.** A duplicate identifier or a row in the
   wrong country is REPORTED (backend/services/registry_audit.py), not refused. The
   defects are the customer's existing data, and telling them precisely which rows
   are broken is the day-one value; a 4xx would leave them believing the file was fine.

3. **An empty register is empty.** No sample fallback lives on this side of the wire.
   A register with no rows returns no rows, and the deck is responsible for saying so
   rather than rendering an all-clear board.

Scoping is by ``OrgDep`` — a membership, resolved once as a dependency. A missed
``org_id`` filter here does not show a user stale data of their own, it shows them
another company's site register, so the filter is never hand-written per handler.
"""

import csv
import io
import logging
import uuid
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.dependencies import DbDep, OrgDep, OrgWriterDep
from backend.countries import to_iso2
from backend.models.site import Site
from backend.services.registry_audit import audit_register

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sites", tags=["sites"])

# 5 MB holds roughly 40,000 register rows. Bounds memory the same way the IMINT
# upload does, and for the same reason: the body is read fully before it is parsed.
_MAX_BYTES = 5 * 1024 * 1024
# Browsers and Excel disagree about what a CSV is, so the allowlist is generous about
# the label and strict about the size. text/plain is included because Windows sends it
# for a .csv with no registry association.
_ALLOWED_TYPES = {
    "text/csv", "application/csv", "text/plain",
    "application/vnd.ms-excel", "application/octet-stream",
}

SITE_TYPES = {"campus", "office", "delivery", "datacentre", "vendor"}
CRITICALITIES = {"tier-1", "tier-2", "tier-3"}

# Header aliases seen in real registers. The canonical name is on the left.
_ALIASES = {
    "external_id": ("external_id", "id", "site_id", "siteid", "code", "site_code", "location_id"),
    "name": ("name", "site", "site_name", "location", "location_name", "office"),
    "city": ("city", "town", "location_city"),
    "country": ("country", "country_name", "nation"),
    "lat": ("lat", "latitude"),
    "lng": ("lng", "lon", "long", "longitude"),
    "type": ("type", "site_type", "category"),
    "criticality": ("criticality", "tier", "importance"),
    "headcount": ("headcount", "head_count", "employees", "staff", "population", "seats"),
}

# Leading characters a spreadsheet will execute rather than display.
_RISKY_LEAD = ("=", "+", "-", "@", "\t", "\r")


class SiteCreate(BaseModel):
    name: str
    external_id: str | None = None
    city: str | None = None
    country: str | None = None
    lat: float | None = None
    lng: float | None = None
    type: str = "office"
    criticality: str = "tier-3"
    headcount: int | None = None


class SiteUpdate(BaseModel):
    name: str | None = None
    external_id: str | None = None
    city: str | None = None
    country: str | None = None
    lat: float | None = None
    lng: float | None = None
    type: str | None = None
    criticality: str | None = None
    headcount: int | None = None


def _serialize(s: Site) -> dict:
    """Field names mirror the deck fixture exactly — see backend/models/site.py."""
    return {
        "id": str(s.id),
        "external_id": s.external_id,
        "name": s.name,
        "city": s.city,
        "country": s.country,
        "lat": s.lat,
        "lng": s.lng,
        "type": s.type,
        "criticality": s.criticality,
        "headcount": s.headcount,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _audit_rows(sites: list[Site]) -> list[dict]:
    """Shape stored rows for the audit, keyed by the identifier the CUSTOMER uses.

    Falling back to our UUID when there is no external_id is deliberate: a row with
    no customer identifier cannot collide with another one, and inventing a shared
    key for them would manufacture duplicate findings that do not exist.
    """
    return [{
        "id": s.external_id or str(s.id),
        "name": s.name, "city": s.city, "country": s.country,
        "lat": s.lat, "lng": s.lng, "headcount": s.headcount,
    } for s in sites]


def _audit(rows: list[dict]) -> dict:
    """Run the register audit, resolving country codes for the names actually present.

    The mapping is built per-call from the register's own countries rather than passed
    as a fixed table, so "INDIA", "india" and "Bharat" all resolve while the audit's
    contract stays identical to its JavaScript twin (a plain name→ISO dict).
    """
    codes = {}
    for r in rows:
        c = r.get("country")
        if c and c not in codes:
            iso = to_iso2(c)
            if iso:
                codes[c] = iso
    return audit_register(rows, country_codes=codes)


def _norm_key(name: str, city) -> str:
    return f"{str(name or '').strip().lower()}|{str(city or '').strip().lower()}"


def _dedupe_key(external_id, name: str, city, ambiguous: set[str]) -> str:
    """The key an import is idempotent on.

    ``external_id`` when the customer gave us one — their own identity for the row,
    which survives a rename. When they did not, fall back to name+city, because the
    alternative is that every re-upload of an id-less register appends a second copy
    of every site. That fallback is weaker (a rename creates a new row) and the
    import response says which key it used.

    🔴 ``ambiguous`` is the whole reason this takes a third argument. A real register
    repeats an identifier — the observed incumbent has AFR08 on two rows in two
    countries — and keying on it alone would collapse those two sites into one. That
    is not deduplication, it is DELETING a site the customer told us about, and the
    only trace would be a headcount that quietly dropped. So an identifier that
    appears more than once (in the file or already in the register) falls back to a
    compound key: both rows are stored, and the audit reports the duplicate. Store
    and report the defect; never silently resolve it.
    """
    eid = str(external_id).strip().lower() if external_id else ""
    if not eid:
        return f"nc:{_norm_key(name, city)}"
    if eid in ambiguous:
        return f"eid:{eid}|{_norm_key(name, city)}"
    return f"eid:{eid}"


def _clean_cell(v):
    """Undo the export's formula-injection guard so a round-trip is lossless.

    Our CSV export prefixes an apostrophe to any value starting = + - @ (the
    spreadsheet-formula characters). If the customer edits that export and sends it
    back — which is the entire point of an export — the apostrophe must come off, or
    a site named "-Central" slowly accretes one on every cycle.
    """
    if v is None:
        return None
    s = str(v).strip()
    if len(s) > 1 and s[0] == "'" and s[1] in _RISKY_LEAD:
        s = s[1:]
    return s


def _num(v, integer: bool = False):
    """Parse a numeric cell, returning None for anything that is not a number.

    None, not 0. A blank latitude is a missing coordinate the audit must flag; a
    zero latitude is Null Island, which the audit flags as a different, more specific
    defect. Collapsing the two would hide which one the customer actually has.
    """
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s:
        return None
    try:
        return int(float(s)) if integer else float(s)
    except ValueError:
        return None


def _map_headers(fieldnames) -> dict[str, str]:
    """Map this file's headers onto our canonical column names."""
    found: dict[str, str] = {}
    for raw in fieldnames or []:
        key = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
        for canon, aliases in _ALIASES.items():
            if key in aliases and canon not in found:
                found[canon] = raw
                break
    return found


@router.get("")
async def list_sites(
    db: DbDep,
    org: OrgDep,
    include_inactive: bool = Query(False),
) -> dict:
    stmt = select(Site).where(Site.org_id == org.org_id)
    if not include_inactive:
        stmt = stmt.where(Site.is_active == True)  # noqa: E712 — repo idiom
    sites = (await db.execute(stmt.order_by(Site.name))).scalars().all()

    return {
        "sites": [_serialize(s) for s in sites],
        "count": len(sites),
        # The audit travels with the register rather than sitting behind its own
        # endpoint, so a deck can never render the numbers without the caveats.
        "audit": _audit(_audit_rows(list(sites))),
    }


@router.post("")
async def create_site(body: SiteCreate, db: DbDep, org: OrgWriterDep) -> dict:
    if body.type not in SITE_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {sorted(SITE_TYPES)}")
    if body.criticality not in CRITICALITIES:
        raise HTTPException(status_code=400, detail=f"criticality must be one of {sorted(CRITICALITIES)}")

    site = Site(
        id=uuid.uuid4(), org_id=org.org_id,
        external_id=body.external_id, name=body.name, city=body.city, country=body.country,
        lat=body.lat, lng=body.lng, type=body.type, criticality=body.criticality,
        headcount=body.headcount, is_active=True,
    )
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return _serialize(site)


@router.patch("/{site_id}")
async def update_site(site_id: uuid.UUID, body: SiteUpdate, db: DbDep, org: OrgWriterDep) -> dict:
    site = await db.get(Site, site_id)
    # Not-yours is answered 404, not 403 — the repo idiom, and it avoids confirming
    # that another organization's site id exists.
    if not site or site.org_id != org.org_id:
        raise HTTPException(status_code=404, detail="Site not found")

    fields = body.model_dump(exclude_unset=True)
    if "type" in fields and fields["type"] not in SITE_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {sorted(SITE_TYPES)}")
    if "criticality" in fields and fields["criticality"] not in CRITICALITIES:
        raise HTTPException(status_code=400, detail=f"criticality must be one of {sorted(CRITICALITIES)}")

    for k, v in fields.items():
        setattr(site, k, v)
    site.updated_at = datetime.now(timezone.utc)
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return _serialize(site)


@router.delete("/{site_id}")
async def delete_site(site_id: uuid.UUID, db: DbDep, org: OrgWriterDep) -> dict:
    site = await db.get(Site, site_id)
    if not site or site.org_id != org.org_id:
        raise HTTPException(status_code=404, detail="Site not found")

    # Soft delete, matching UserFollow. A closed site still has history attached to
    # it — trips that went there, alerts that named it — and hard-deleting the row
    # would orphan all of it.
    site.is_active = False
    site.updated_at = datetime.now(timezone.utc)
    db.add(site)
    await db.commit()
    return {"deleted": True, "id": str(site_id)}


@router.post("/import")
async def import_sites(
    db: DbDep,
    org: OrgWriterDep,
    file: UploadFile = File(...),
    dry_run: bool = Query(False, description="Audit and report, but write nothing."),
) -> dict:
    """Import a site register from CSV. Idempotent per row; audited on arrival.

    ``dry_run=true`` returns the identical report without writing, so a customer can
    see what their file does to their register before it does it.
    """
    media_type = (file.content_type or "").lower().split(";")[0].strip()
    if media_type and media_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload a CSV file.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB).")

    try:
        # utf-8-sig strips the BOM Excel writes — otherwise the first header comes
        # back as "﻿id" and every row silently loses its identifier.
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("cp1252")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File is not readable text (UTF-8 or Windows-1252).")

    reader = csv.DictReader(io.StringIO(text))
    headers = _map_headers(reader.fieldnames)
    if "name" not in headers:
        raise HTTPException(
            status_code=400,
            detail=("No site-name column found. Expected one of: "
                    f"{', '.join(_ALIASES['name'])}. Found: "
                    f"{', '.join(str(f) for f in (reader.fieldnames or [])) or 'nothing'}."),
        )

    parsed: list[dict] = []
    rejected: list[dict] = []
    for line_no, raw in enumerate(reader, start=2):  # 1 is the header
        def cell(canon):
            return _clean_cell(raw.get(headers[canon])) if canon in headers else None

        name = cell("name")
        if not name:
            # A nameless row cannot be shown, joined or acted on. It is reported by
            # line number rather than dropped in silence.
            rejected.append({"line": line_no, "reason": "No site name on this row"})
            continue

        site_type = (cell("type") or "office").lower()
        crit = (cell("criticality") or "tier-3").lower()
        parsed.append({
            "line": line_no,
            "external_id": cell("external_id") or None,
            "name": name,
            "city": cell("city") or None,
            "country": cell("country") or None,
            "lat": _num(cell("lat")),
            "lng": _num(cell("lng")),
            "type": site_type if site_type in SITE_TYPES else "office",
            "criticality": crit if crit in CRITICALITIES else "tier-3",
            "headcount": _num(cell("headcount"), integer=True),
        })

    if not parsed:
        raise HTTPException(status_code=400, detail="No usable rows in this file.")

    # The audit runs on what the FILE says, before anything is written, so the report
    # describes the customer's data rather than our reconciliation of it.
    audit = _audit([{
        "id": p["external_id"] or f"line-{p['line']}",
        "name": p["name"], "city": p["city"], "country": p["country"],
        "lat": p["lat"], "lng": p["lng"], "headcount": p["headcount"],
    } for p in parsed])

    existing = (await db.execute(
        select(Site).where(Site.org_id == org.org_id)
    )).scalars().all()

    # An identifier is ambiguous if it repeats ANYWHERE — in the incoming file or in
    # the register already. Both sides must agree on the verdict, or a file carrying
    # AFR08 twice would key its rows differently from the single AFR08 already stored
    # and orphan it.
    file_counts = Counter(str(p["external_id"]).strip().lower()
                          for p in parsed if p["external_id"])
    stored_counts = Counter(str(s.external_id).strip().lower()
                            for s in existing if s.external_id)
    ambiguous = {e for e in set(file_counts) | set(stored_counts)
                 if file_counts[e] > 1 or stored_counts[e] > 1}

    by_key = {_dedupe_key(s.external_id, s.name, s.city, ambiguous): s for s in existing}

    created = updated = unchanged = 0
    # An in-batch seen-set, because a SELECT cannot see rows added earlier in the same
    # uncommitted batch — the same trap hazard_ingest_worker hit. Without it, a file
    # containing the same site twice inserts it twice.
    seen: dict[str, Site] = {}
    failures: list[dict] = []

    for p in parsed:
        key = _dedupe_key(p["external_id"], p["name"], p["city"], ambiguous)
        target = seen.get(key) or by_key.get(key)
        try:
            # Per-row SAVEPOINT: one bad row must not poison the session and cost the
            # customer the other 199 sites in their file.
            async with db.begin_nested():
                if target is None:
                    site = Site(
                        id=uuid.uuid4(), org_id=org.org_id,
                        external_id=p["external_id"], name=p["name"], city=p["city"],
                        country=p["country"], lat=p["lat"], lng=p["lng"],
                        type=p["type"], criticality=p["criticality"],
                        headcount=p["headcount"], is_active=True,
                    )
                    db.add(site)
                    seen[key] = site
                    created += 1
                else:
                    changes = {
                        "name": p["name"], "city": p["city"], "country": p["country"],
                        "lat": p["lat"], "lng": p["lng"], "type": p["type"],
                        "criticality": p["criticality"], "headcount": p["headcount"],
                        "external_id": p["external_id"] or target.external_id,
                    }
                    dirty = [k for k, v in changes.items() if getattr(target, k) != v]
                    # A re-imported row that reactivates a soft-deleted site IS a change.
                    if not target.is_active:
                        dirty.append("is_active")
                    if dirty:
                        for k, v in changes.items():
                            setattr(target, k, v)
                        target.is_active = True
                        target.updated_at = datetime.now(timezone.utc)
                        db.add(target)
                        updated += 1
                    else:
                        unchanged += 1
                    seen[key] = target
        except Exception as exc:  # noqa: BLE001 — one row must not end the import
            logger.warning("Site import row %s failed: %s", p["line"], exc)
            failures.append({"line": p["line"], "reason": str(exc)[:200]})

    if dry_run:
        await db.rollback()
    else:
        await db.commit()

    return {
        "dry_run": dry_run,
        "rows_read": len(parsed) + len(rejected),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "rejected": rejected,
        "failed": failures,
        # Named so the customer can see WHY two rows were, or were not, treated as
        # one site — and which of their identifiers were too ambiguous to key on.
        "matched_on": "external_id" if any(p["external_id"] for p in parsed) else "name+city",
        "ambiguous_identifiers": sorted(ambiguous),
        "audit": audit,
    }


def _csv_cell(value) -> str:
    """Mirror of ``csvCell`` in web/src/lib/deckFilters.js.

    The apostrophe prefix is not decoration: a site name a customer typed as
    ``=cmd|' /c calc'!A1`` is untrusted input that executes when their colleague
    opens the export. ``_clean_cell`` removes the prefix again on re-import.
    """
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in _RISKY_LEAD:
        s = "'" + s
    if any(c in s for c in '",\n\r'):
        s = '"' + s.replace('"', '""') + '"'
    return s


@router.get("/export")
async def export_sites(db: DbDep, org: OrgDep) -> Response:
    sites = (await db.execute(
        select(Site).where(Site.org_id == org.org_id).where(Site.is_active == True)  # noqa: E712
        .order_by(Site.name)
    )).scalars().all()

    cols = ["external_id", "name", "city", "country", "lat", "lng",
            "type", "criticality", "headcount"]
    lines = [",".join(_csv_cell(c) for c in cols)]
    for s in sites:
        lines.append(",".join(_csv_cell(getattr(s, c)) for c in cols))

    # BOM so Excel opens UTF-8 site names correctly instead of mojibake — the same
    # reason downloadCSV writes one on the browser side.
    body = "﻿" + "\r\n".join(lines)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="sites.csv"'},
    )
