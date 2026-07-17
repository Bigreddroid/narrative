"""
IMINT → event composition: turn an interpreted image into a real event on the graph.

Phase 2e shipped a working IMINT interpreter and a working geolocator, but both were
analytical dead-ends: they returned a read-out to the caller and persisted nothing. An
operator could get an excellent OODA-traced assessment of an image and it would vanish
when the response closed — never a globe pin, never a graph node, never available to
corroborate anything. Every other discipline on the platform produces events; IMINT
alone produced a paragraph.

This module closes that gap by composing the two vision paths that already exist:

    services/imint.py      → WHAT the image shows
    services/geolocate.py  → WHERE it was taken
    build_signal(...)      → an event signal the normal ingest path can persist

The honesty gate is the whole point. An interpretation we cannot place, or can only
place on a low-confidence guess, does NOT become a pin — it is returned to the operator
as a read-out and nothing is written. A fabricated coordinate is far worse than a
missing one: it would corroborate other disciplines in space+time on the /int fusion
strip and manufacture confidence out of nothing.

$0/local doctrine: pure function, no I/O, no LLM. The two vision calls happen upstream.
"""

import hashlib

from backend import taxonomy
from backend.services import llm

# Provenance for every event this path creates. Registered in taxonomy.SOURCE_DISCIPLINE
# so discipline_for() resolves it to IMINT the same deterministic way a USGS feed
# resolves to MASINT — the discipline is never hand-set on the event.
SOURCE = "imint"

# Below this geolocation confidence we decline to place the image at all. A pin is a
# claim about the physical world; an unconfident pin is a lie the fusion engine would
# then treat as evidence.
MIN_LOCATION_CONFIDENCE = 0.35

# A single operator-supplied photo is real intelligence but thin evidence — it must
# never outrank a measured M7 earthquake or a live conflict event in the feed.
IMPORTANCE_CEILING = 70

# How the two confidences combine. The interpretation carries more of the meaning, but
# a shaky location still drags the whole event down: an assessment we can't place well
# is worth less, because its value here is being fused in space and time.
_INTERPRETATION_WEIGHT = 0.6
_LOCATION_WEIGHT = 0.4


def image_sha256(data: bytes) -> str:
    """Stable identity for an uploaded image.

    Used as the event's external_id so the ingest path's existing (source, external_id)
    dedupe applies for free: re-uploading the same photo refreshes the existing event
    instead of littering the globe with duplicate pins of one image.
    """
    return hashlib.sha256(data).hexdigest()


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # reject NaN


def _conf(v) -> float:
    # Upstream services already normalize, but this is the gate that decides whether a
    # pin is real — it must not be the place a percent answer sneaks through.
    return llm.normalize_confidence(v)


def _no(reason: str) -> dict:
    return {"ok": False, "reason": reason, "signal": None}


def build_signal(interpretation: dict, location: dict, image_sha: str) -> dict:
    """Compose an IMINT interpretation + geolocation into a persistable event signal.

    Returns {"ok": True, "signal": {...}} when the pair is well-evidenced enough to
    earn a real event, else {"ok": False, "reason": <operator-readable>, "signal": None}.
    The signal dict matches the shape the hazard ingest path already consumes.
    """
    interpretation = interpretation or {}
    location = location or {}

    if interpretation.get("available") is not True:
        return _no("No event was created: the image interpretation is unavailable.")

    best = interpretation.get("best") or {}
    assessment = str(best.get("assessment") or "").strip()
    if not assessment:
        return _no("No event was created: the interpretation carries no assessment.")

    if location.get("available") is not True:
        return _no("No event was created: the image could not be located, so it cannot "
                   "be placed on the globe.")

    place_best = location.get("best") or {}
    lat, lng = _num(place_best.get("lat")), _num(place_best.get("lng"))
    if lat is None or lng is None:
        return _no("No event was created: the geolocation returned no usable coordinates.")
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return _no("No event was created: the geolocation returned out-of-range coordinates.")

    location_confidence = _conf(place_best.get("confidence"))
    if location_confidence < MIN_LOCATION_CONFIDENCE:
        return _no(
            f"No event was created: the location confidence ({location_confidence:.2f}) is "
            f"below the {MIN_LOCATION_CONFIDENCE:.2f} floor — the read-out stands, but we "
            f"will not pin a guess to the map."
        )

    interpretation_confidence = _conf(best.get("confidence"))
    place = str(place_best.get("place") or "").strip()
    country = str(place_best.get("country") or "").strip()
    facility_type = str(best.get("facility_type") or "").strip()
    activity = str(best.get("activity") or "").strip()
    why = str(best.get("why") or "").strip()

    where = place or country or f"{lat:.3f}, {lng:.3f}"
    title = f"{assessment} — {where}"[:240]

    summary_parts = [f"IMINT interpretation of operator-supplied imagery: {assessment}."]
    if why:
        summary_parts.append(f"Visual rationale: {why}.")
    if facility_type:
        summary_parts.append(f"Facility type: {facility_type}.")
    if activity:
        summary_parts.append(f"Activity observed: {activity}.")
    summary_parts.append(
        f"Placed at {where} ({lat:.4f}, {lng:.4f}) with {location_confidence:.0%} location "
        f"confidence and {interpretation_confidence:.0%} interpretation confidence."
    )
    summary_parts.append(interpretation.get("scope") or "")

    weighted = (_INTERPRETATION_WEIGHT * interpretation_confidence
                + _LOCATION_WEIGHT * location_confidence)

    return {
        "ok": True,
        "reason": None,
        "signal": {
            "title": title,
            "summary": " ".join(p for p in summary_parts if p).strip(),
            # Left unset on purpose: a photo does not reliably imply a feed category, and
            # inventing one would be fabrication. The discipline does not depend on it —
            # SOURCE resolves to IMINT on provenance alone (see taxonomy.discipline_for).
            "category": None,
            "importance": round(IMPORTANCE_CEILING * weighted),
            "status": "developing",
            "geography": [g for g in (country, place) if g],
            "lat": lat,
            "lng": lng,
            "source": SOURCE,
            "external_id": image_sha,
        },
    }


# Drift guard: this path's whole contract is that its events read as IMINT through the
# same deterministic taxonomy as every other event. If SOURCE ever falls out of
# SOURCE_DISCIPLINE, these events would silently default to HUMINT and the /int IMINT
# panel would stay empty for a reason nobody could see. Fail loudly at import instead.
assert taxonomy.discipline_for(SOURCE, None) == taxonomy.IMINT, (
    f"taxonomy.SOURCE_DISCIPLINE must map {SOURCE!r} → IMINT"
)
