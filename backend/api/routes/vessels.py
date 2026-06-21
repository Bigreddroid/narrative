"""
Maritime vessel feed — server-side AIS source for the maritime map overlay.

Polls AISHub (https://www.aishub.net/api) when AISHUB_USERNAME is configured,
normalises records, and serves them from a 60s cache (AISHub enforces a hard
1-request-per-minute limit). Keeping this server-side avoids browser CORS issues
and never exposes the AIS credentials to the client.

If no source is configured the endpoint returns an empty list with source="none",
so the frontend transparently falls back to AISStream → simulated.
"""

import logging
import time

import httpx
from fastapi import APIRouter, Query

from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vessels", tags=["vessels"])
settings = get_settings()

AISHUB_URL = "https://data.aishub.net/ws.php"
CACHE_TTL = 60.0  # seconds — AISHub allows at most one request per minute

# Module-level cache: { bbox_key: (timestamp, vessels) } + a global throttle.
_cache: dict[str, tuple[float, list[dict]]] = {}
_last_fetch = 0.0


def _bucket(ais_type) -> str:
    """Map an AIS ship-type code to a coarse bucket (matches the frontend)."""
    try:
        code = int(ais_type)
    except (TypeError, ValueError):
        return "other"
    if 60 <= code <= 69:
        return "passenger"
    if 70 <= code <= 79:
        return "cargo"
    if 80 <= code <= 89:
        return "tanker"
    if code == 30:
        return "fishing"
    return "other"


def _normalize(rec: dict) -> dict | None:
    lat = rec.get("LATITUDE")
    lng = rec.get("LONGITUDE")
    if lat is None or lng is None:
        return None
    heading = rec.get("HEADING")
    if heading in (None, 511):  # 511 = "not available"
        heading = rec.get("COG") or 0
    return {
        "mmsi": rec.get("MMSI"),
        "name": (rec.get("NAME") or "").strip() or f"MMSI {rec.get('MMSI', '?')}",
        "type": _bucket(rec.get("TYPE")),
        "lat": lat,
        "lng": lng,
        "heading": heading,
        "sog": rec.get("SOG") or 0,
    }


async def _fetch_aishub(latmin, latmax, lonmin, lonmax) -> list[dict]:
    params = {
        "username": settings.aishub_username,
        "format": 1,        # human-readable named fields
        "output": "json",
        "compress": 0,
        "latmin": latmin, "latmax": latmax, "lonmin": lonmin, "lonmax": lonmax,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(AISHUB_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    # AISHub returns [ {meta}, [ {record}, ... ] ]
    if not isinstance(data, list) or len(data) < 2:
        meta = data[0] if isinstance(data, list) and data else {}
        logger.warning("AISHub returned no records: %s", meta)
        return []
    meta, records = data[0], data[1]
    if isinstance(meta, dict) and meta.get("ERROR"):
        logger.warning("AISHub error: %s", meta.get("ERROR_MESSAGE"))
        return []
    vessels = [v for r in records if (v := _normalize(r))]
    return vessels


def cached_vessels() -> list[dict]:
    """Vessels currently in the module cache, deduped by MMSI. No network call —
    used by the exposure route to derive the Chokepoint Congestion Index from
    whatever AIS positions the maritime overlay has already pulled."""
    seen: dict = {}
    for _ts, vessels in _cache.values():
        for v in vessels:
            seen[v.get("mmsi") or id(v)] = v
    return list(seen.values())


@router.get("")
async def get_vessels(
    latmin: float = Query(-90), latmax: float = Query(90),
    lonmin: float = Query(-180), lonmax: float = Query(180),
) -> dict:
    """Return live vessel positions from the configured AIS source (cached 60s)."""
    global _last_fetch

    if not settings.aishub_username:
        return {"vessels": [], "source": "none", "live": False}

    key = f"{latmin:.1f},{latmax:.1f},{lonmin:.1f},{lonmax:.1f}"
    now = time.monotonic()

    cached = _cache.get(key)
    if cached and now - cached[0] < CACHE_TTL:
        return {"vessels": cached[1], "source": "aishub", "live": True}

    # Respect AISHub's 1-request-per-minute limit across all bboxes.
    if now - _last_fetch < CACHE_TTL:
        return {"vessels": cached[1] if cached else [], "source": "aishub", "live": True}

    try:
        vessels = await _fetch_aishub(latmin, latmax, lonmin, lonmax)
        _last_fetch = now
        _cache[key] = (now, vessels)
        return {"vessels": vessels, "source": "aishub", "live": True}
    except Exception as exc:  # noqa: BLE001 — degrade gracefully, never 500 the map
        logger.warning("AISHub fetch failed: %s", exc)
        return {"vessels": cached[1] if cached else [], "source": "aishub", "live": True}
