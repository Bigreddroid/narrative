"""
People and trips — who the customer owes a duty of care to, and where they are.

A security platform is judged on people, not events: liability attaches to a person
standing somewhere, and "how many of ours are exposed" is the question a board asks.
Until now the executive deck answered it from 42 invented itineraries in a browser
fixture.

🔴 The join this route exists to fix. ``ExecDeck.jsx`` matches travellers to sites
with ``trip.to === office.city`` — string equality on a city NAME. That works only
because both sides come from the same fixture; against real data a site called
"Bengaluru — Electronic City" never equals a trip to "Bengaluru", and the traveller
panel goes quietly empty while every other number on the page still looks right.
So each trip carries ``toSiteId``, and the deck joins on that. ``to`` remains in the
payload for display and for the fixture-shaped fallback, never as the join key.

Trip payloads mirror ``SAMPLE_TRIPS`` field for field (``traveler``, ``role``,
``from``, ``to``, ``country``, ``toLat``, ``toLng``, ``departISO``, ``returnISO``,
``lastCheckInISO``) so ``travelPosture()`` and the deck's travel table keep working
unchanged when the fixture is swapped. MOCK THE DATA, NEVER THE SHAPE.
"""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.dependencies import DbDep, OrgDep, OrgWriterDep
from backend.models.person import Person, Trip
from backend.models.site import Site

router = APIRouter(prefix="/people", tags=["people"])


class PersonCreate(BaseModel):
    name: str
    email: str | None = None
    role: str | None = None
    home_site_id: uuid.UUID | None = None


class PersonUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    role: str | None = None
    home_site_id: uuid.UUID | None = None


class TripCreate(BaseModel):
    person_id: uuid.UUID
    from_site_id: uuid.UUID | None = None
    to_site_id: uuid.UUID | None = None
    to_city: str | None = None
    to_country: str | None = None
    to_lat: float | None = None
    to_lng: float | None = None
    depart_date: date | None = None
    return_date: date | None = None


class TripUpdate(BaseModel):
    from_site_id: uuid.UUID | None = None
    to_site_id: uuid.UUID | None = None
    to_city: str | None = None
    to_country: str | None = None
    to_lat: float | None = None
    to_lng: float | None = None
    depart_date: date | None = None
    return_date: date | None = None
    check_in: bool | None = None


def _serialize_person(p: Person) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "email": p.email,
        "role": p.role,
        "home_site_id": str(p.home_site_id) if p.home_site_id else None,
    }


def _serialize_trip(t: Trip, person: Person | None, to_site: Site | None,
                    from_site: Site | None) -> dict:
    """Fixture-shaped, with the real ids alongside.

    ``to``/``country``/``toLat``/``toLng`` fall back to the destination SITE when the
    trip did not carry them, so a trip booked against a known office does not have to
    repeat what the register already knows — and cannot disagree with it.
    """
    return {
        "id": str(t.id),
        "personId": str(t.person_id),
        "traveler": person.name if person else None,
        "role": person.role if person else None,
        "from": (from_site.city or from_site.name) if from_site else None,
        "fromSiteId": str(t.from_site_id) if t.from_site_id else None,
        # The join key. `to` is display text; this is what the deck matches on.
        "toSiteId": str(t.to_site_id) if t.to_site_id else None,
        "to": t.to_city or (to_site.city if to_site else None),
        "country": t.to_country or (to_site.country if to_site else None),
        "toLat": t.to_lat if t.to_lat is not None else (to_site.lat if to_site else None),
        "toLng": t.to_lng if t.to_lng is not None else (to_site.lng if to_site else None),
        "departISO": t.depart_date.isoformat() if t.depart_date else None,
        "returnISO": t.return_date.isoformat() if t.return_date else None,
        "lastCheckInISO": t.last_check_in_at.isoformat() if t.last_check_in_at else None,
    }


async def _owned_site(db, org, site_id: uuid.UUID | None) -> Site | None:
    """Resolve a site id, refusing one that belongs to another organization.

    Without this a caller could attach their traveller to a competitor's site id and
    have the deck join them together. Foreign keys enforce that the row EXISTS; only
    this check enforces that it is theirs.
    """
    if site_id is None:
        return None
    site = await db.get(Site, site_id)
    if not site or site.org_id != org.org_id:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("")
async def list_people(db: DbDep, org: OrgDep) -> dict:
    people = (await db.execute(
        select(Person).where(Person.org_id == org.org_id)
        .where(Person.is_active == True)  # noqa: E712 — repo idiom
        .order_by(Person.name)
    )).scalars().all()
    return {"people": [_serialize_person(p) for p in people], "count": len(people)}


@router.post("")
async def create_person(body: PersonCreate, db: DbDep, org: OrgWriterDep) -> dict:
    await _owned_site(db, org, body.home_site_id)
    person = Person(
        id=uuid.uuid4(), org_id=org.org_id, name=body.name, email=body.email,
        role=body.role, home_site_id=body.home_site_id, is_active=True,
    )
    db.add(person)
    await db.commit()
    await db.refresh(person)
    return _serialize_person(person)


@router.patch("/{person_id}")
async def update_person(person_id: uuid.UUID, body: PersonUpdate, db: DbDep,
                        org: OrgWriterDep) -> dict:
    person = await db.get(Person, person_id)
    if not person or person.org_id != org.org_id:
        raise HTTPException(status_code=404, detail="Person not found")

    fields = body.model_dump(exclude_unset=True)
    if "home_site_id" in fields:
        await _owned_site(db, org, fields["home_site_id"])
    for k, v in fields.items():
        setattr(person, k, v)
    person.updated_at = datetime.now(timezone.utc)
    db.add(person)
    await db.commit()
    await db.refresh(person)
    return _serialize_person(person)


@router.delete("/{person_id}")
async def delete_person(person_id: uuid.UUID, db: DbDep, org: OrgWriterDep) -> dict:
    person = await db.get(Person, person_id)
    if not person or person.org_id != org.org_id:
        raise HTTPException(status_code=404, detail="Person not found")
    person.is_active = False
    person.updated_at = datetime.now(timezone.utc)
    db.add(person)
    await db.commit()
    return {"deleted": True, "id": str(person_id)}


# ── trips ────────────────────────────────────────────────────────────────────
# Mounted under /people because a trip has no meaning without its traveller, and a
# GSOC reads them together.

@router.get("/trips")
async def list_trips(
    db: DbDep,
    org: OrgDep,
    window_days: int = Query(90, ge=1, le=365,
                             description="Include trips returning within this many days."),
) -> dict:
    """Trips in the forward window, plus anyone still out from before it.

    The filter is on ``return_date``, not ``depart_date``: a traveller who left two
    months ago and has not come back is exactly the person a duty-of-care platform
    must not drop off the list.
    """
    horizon = date.today().toordinal() + window_days
    stmt = (
        select(Trip).where(Trip.org_id == org.org_id)
        .where(Trip.is_active == True)  # noqa: E712
        .order_by(Trip.depart_date)
    )
    trips = (await db.execute(stmt)).scalars().all()
    trips = [t for t in trips
             if t.return_date is None or t.return_date.toordinal() <= horizon]

    people = {p.id: p for p in (await db.execute(
        select(Person).where(Person.org_id == org.org_id)
    )).scalars().all()}
    sites = {s.id: s for s in (await db.execute(
        select(Site).where(Site.org_id == org.org_id)
    )).scalars().all()}

    return {"trips": [
        _serialize_trip(t, people.get(t.person_id), sites.get(t.to_site_id),
                        sites.get(t.from_site_id))
        for t in trips
    ], "count": len(trips)}


@router.post("/trips")
async def create_trip(body: TripCreate, db: DbDep, org: OrgWriterDep) -> dict:
    person = await db.get(Person, body.person_id)
    if not person or person.org_id != org.org_id:
        raise HTTPException(status_code=404, detail="Person not found")

    to_site = await _owned_site(db, org, body.to_site_id)
    from_site = await _owned_site(db, org, body.from_site_id)

    if body.depart_date and body.return_date and body.return_date < body.depart_date:
        raise HTTPException(status_code=400, detail="Return date is before the departure date")
    # A trip with no destination cannot be scored against anything — neither a site
    # nor a coordinate. Refused rather than stored as an itinerary that silently
    # never matches an event.
    if to_site is None and not body.to_city and body.to_lat is None:
        raise HTTPException(
            status_code=400,
            detail="A trip needs a destination: a site, a city, or coordinates.",
        )

    trip = Trip(
        id=uuid.uuid4(), org_id=org.org_id, person_id=body.person_id,
        from_site_id=body.from_site_id, to_site_id=body.to_site_id,
        to_city=body.to_city, to_country=body.to_country,
        to_lat=body.to_lat, to_lng=body.to_lng,
        depart_date=body.depart_date, return_date=body.return_date, is_active=True,
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)
    return _serialize_trip(trip, person, to_site, from_site)


@router.patch("/trips/{trip_id}")
async def update_trip(trip_id: uuid.UUID, body: TripUpdate, db: DbDep,
                      org: OrgWriterDep) -> dict:
    trip = await db.get(Trip, trip_id)
    if not trip or trip.org_id != org.org_id:
        raise HTTPException(status_code=404, detail="Trip not found")

    fields = body.model_dump(exclude_unset=True)
    check_in = fields.pop("check_in", None)
    if "to_site_id" in fields:
        await _owned_site(db, org, fields["to_site_id"])
    if "from_site_id" in fields:
        await _owned_site(db, org, fields["from_site_id"])

    for k, v in fields.items():
        setattr(trip, k, v)
    if check_in:
        # Set server-side, never from the client. A check-in is a claim about WHEN
        # someone was last accounted for; letting the caller supply the timestamp
        # would let a stale client mark an unaccounted traveller as safe.
        trip.last_check_in_at = datetime.now(timezone.utc)
    if trip.depart_date and trip.return_date and trip.return_date < trip.depart_date:
        raise HTTPException(status_code=400, detail="Return date is before the departure date")

    trip.updated_at = datetime.now(timezone.utc)
    db.add(trip)
    await db.commit()
    await db.refresh(trip)

    person = await db.get(Person, trip.person_id)
    to_site = await db.get(Site, trip.to_site_id) if trip.to_site_id else None
    from_site = await db.get(Site, trip.from_site_id) if trip.from_site_id else None
    return _serialize_trip(trip, person, to_site, from_site)


@router.delete("/trips/{trip_id}")
async def delete_trip(trip_id: uuid.UUID, db: DbDep, org: OrgWriterDep) -> dict:
    trip = await db.get(Trip, trip_id)
    if not trip or trip.org_id != org.org_id:
        raise HTTPException(status_code=404, detail="Trip not found")
    trip.is_active = False
    trip.updated_at = datetime.now(timezone.utc)
    db.add(trip)
    await db.commit()
    return {"deleted": True, "id": str(trip_id)}
