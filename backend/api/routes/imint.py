"""
IMINT — POST /api/v1/imint.

Upload an image the operator already has; get back an imagery-intelligence read-out
(what it shows + the OODA reasoning trace, see backend/services/imint.py) AND, when the
image can be honestly placed, a real event on the graph and globe.

Persisting is the point. An interpretation that only ever returns to the caller is an
analytical dead-end: it can never pin, never link, never corroborate another discipline.
So when persist=true (the default) this endpoint also runs the geolocator and composes
the two into an event via services/imint_event.py — written through the SAME ingest path
every feed uses, so IMINT gets the same dedupe, consequence map, embedding and graph
linkage as any other event rather than a parallel back door.

The read-out is returned either way. A failure to place the image degrades to
event.persisted=false with a reason; it never fabricates a coordinate, and it never
costs the operator the interpretation they already have.

Re-uploads are answered hash-first: the sha256 of the bytes is checked against
existing IMINT events BEFORE any vision call, so the same photo never burns a second
pair of multi-minute llava passes — the response carries deduped=true and the
existing event id instead of a fresh trace.

Scope is honestly bounded: interpretation of provided imagery only — no satellite
tasking, no commercial-imagery purchase. Paid-tier feature. Runs free on a local
multimodal model or Claude vision when paid APIs are enabled; degrades to an honest
"unavailable" result instead of fabricating an assessment.
"""

import asyncio
import base64
import logging

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from sqlalchemy import select

from backend.api.dependencies import DbDep, UserDep
from backend.models.narrative_event import NarrativeEvent
from backend.services import cost_guard, geolocate, imint, imint_event
# The canonical event-creation path. Imported rather than reimplemented so IMINT events
# are built exactly like every other event — osint_ingest_worker reuses it the same way.
from backend.workers.hazard_ingest_worker import _upsert

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/imint", tags=["imint"])

_MAX_BYTES = 8 * 1024 * 1024  # 8 MB — generous for a photo/frame, bounds memory/cost
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


async def _existing_event_id(db, sha: str) -> str | None:
    """The event a previous upload of this exact image already created, if any.

    A vision pass costs minutes on CPU, and the ingest path's (source, external_id)
    dedupe only kicks in AFTER both calls have been burned. The sha256 is computed
    from the uploaded bytes before any model runs, so a re-upload is answered from
    the database instead. A fold points at its canonical, same as _persist below.
    """
    row = (await db.execute(
        select(NarrativeEvent)
        .where(NarrativeEvent.source == imint_event.SOURCE)
        .where(NarrativeEvent.external_id == sha)
    )).scalars().first()
    if row is None:
        return None
    return str(row.merged_into_id or row.id)


async def _persist(interpretation: dict, image_b64: str, media_type: str, sha: str, db) -> dict:
    """Place the interpreted image and write it as an event. Never raises: a failure
    here costs the operator the pin, never the interpretation."""
    try:
        # geolocate() wraps a synchronous, blocking vision call — offload it.
        location = await asyncio.to_thread(geolocate.geolocate, image_b64, media_type)
    except Exception as exc:  # noqa: BLE001 — the service degrades internally; this is a net
        logger.warning("IMINT geolocation leg failed: %s", exc)
        return {"persisted": False, "reason": "The image could not be located.", "location": None}

    built = imint_event.build_signal(interpretation, location, sha)
    if not built["ok"]:
        return {"persisted": False, "reason": built["reason"], "location": location}

    try:
        await _upsert(built["signal"], db, require_geo=True)
        await db.commit()
        # Resolve the row back so the operator can click through to their pin. A fold
        # (the same scene re-read into an identical assessment) points at the canonical,
        # which is the event they should actually land on.
        row = (await db.execute(
            select(NarrativeEvent)
            .where(NarrativeEvent.source == imint_event.SOURCE)
            .where(NarrativeEvent.external_id == sha)
        )).scalars().first()
        event_id = str(row.merged_into_id or row.id) if row else None
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.error("IMINT event persist failed: %s", exc)
        return {"persisted": False, "reason": "The event could not be saved.", "location": location}

    return {"persisted": True, "reason": None, "event_id": event_id, "location": location}


@router.post("")
async def interpret_image(
    db: DbDep,
    user: UserDep,
    file: UploadFile = File(...),
    persist: bool = Query(True, description="Also place the image and write it as an event."),
) -> dict:
    if user.tier == "free":
        raise HTTPException(status_code=402, detail="Imagery interpretation is a paid feature.")

    media_type = (file.content_type or "").lower()
    if media_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, WebP or GIF image.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 8 MB).")

    # Hash-first dedupe, BEFORE any vision call: two llava passes cost minutes on CPU,
    # so a re-upload of bytes we already interpreted is answered from the database.
    # Deliberately ahead of the cost guard too — returning an existing event spends
    # nothing, so it works even while the LLM budget is exhausted. persist=false is
    # an explicit request for a fresh read-out and skips this.
    sha = imint_event.image_sha256(data)
    if persist:
        existing_id = await _existing_event_id(db, sha)
        if existing_id is not None:
            return {
                "available": True,
                "deduped": True,
                "scope": imint.SCOPE_NOTE,
                "event": {
                    "persisted": True,
                    "reason": "This exact image was already interpreted; returning its existing event.",
                    "event_id": existing_id,
                },
            }

    # Blocks paid spend unless the active provider is free OR within the hard cap.
    if not await cost_guard.llm_allowed(db):
        raise HTTPException(status_code=503, detail="IMINT is temporarily unavailable (LLM budget or model offline).")

    image_b64 = base64.b64encode(data).decode("ascii")
    try:
        # interpret() wraps a synchronous, blocking vision call — offload it.
        interpretation = await asyncio.to_thread(imint.interpret, image_b64, media_type)
    except Exception as exc:  # noqa: BLE001 — safety net; the service degrades internally
        logger.error("IMINT interpretation failed: %s", exc)
        raise HTTPException(status_code=502, detail="The IMINT interpreter is unavailable right now.")

    if not persist:
        return interpretation
    if interpretation.get("available") is not True:
        # Nothing to place — don't spend a second vision call on it.
        return {**interpretation,
                "event": {"persisted": False, "reason": "No assessment to place."}}

    outcome = await _persist(interpretation, image_b64, media_type, sha, db)
    location = outcome.pop("location", None)
    return {**interpretation, "location": location, "event": outcome}
