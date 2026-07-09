"""
Air-traffic feed — server-side OpenSky source for the air-traffic map overlay.

Polls the OpenSky Network REST API (https://opensky-network.org/apidoc/). Works
anonymously (tight rate limits) or with OPENSKY_USERNAME/PASSWORD for higher
limits. Served from a 15s cache; kept server-side to avoid browser CORS and to
keep any credentials off the client.

If the source is unreachable the endpoint returns an empty list with source="none",
so the frontend transparently falls back to its simulated fleet.
"""

import logging
import time

import httpx
from fastapi import APIRouter, Query

from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/aircraft", tags=["aircraft"])
settings = get_settings()

OPENSKY_URL = "https://opensky-network.org/api/states/all"
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/"
    "protocol/openid-connect/token"
)
CACHE_TTL = 15.0          # seconds — respect OpenSky's anonymous rate limits
MAX_AIRCRAFT = 500        # cap payload size
MS_TO_KNOTS = 1.94384
M_TO_FEET = 3.28084

_cache: dict[str, tuple[float, list[dict]]] = {}
_last_fetch = 0.0

# OAuth2 access token cache: (token, expires_at_monotonic). Tokens live ~30 min;
# we refresh a minute early. Empty token ⇒ not yet fetched / no client creds.
_token: tuple[str, float] = ("", 0.0)


async def _opensky_token(client: httpx.AsyncClient) -> str:
    """Return a valid OAuth2 bearer token (client-credentials), cached until
    shortly before expiry. Empty string when no client creds are configured."""
    global _token
    if not (settings.opensky_client_id and settings.opensky_client_secret):
        return ""
    tok, exp = _token
    if tok and time.monotonic() < exp:
        return tok
    resp = await client.post(
        OPENSKY_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.opensky_client_id,
            "client_secret": settings.opensky_client_secret,
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    tok = payload["access_token"]
    # Refresh 60s before the stated expiry (default 1800s) to avoid edge misses.
    _token = (tok, time.monotonic() + max(payload.get("expires_in", 1800) - 60, 60))
    return tok


def _normalize(state: list) -> dict | None:
    """Map an OpenSky state-vector array to our render record."""
    # [0]icao24 [1]callsign [2]country [5]lon [6]lat [7]baro_alt [8]on_ground [9]vel [10]track
    if len(state) < 11:
        return None
    lat, lng = state[6], state[5]
    if lat is None or lng is None or state[8]:  # skip missing pos / on-ground
        return None
    return {
        "icao": state[0],
        "callsign": (state[1] or "").strip(),
        "country": state[2],
        "lat": lat,
        "lng": lng,
        "alt": round((state[7] or 0) * M_TO_FEET),
        "velocity": round((state[9] or 0) * MS_TO_KNOTS),
        "heading": state[10] or 0,
    }


async def _fetch_opensky(lamin, lamax, lomin, lomax) -> list[dict]:
    params = {"lamin": lamin, "lamax": lamax, "lomin": lomin, "lomax": lomax}
    async with httpx.AsyncClient(timeout=20) as client:
        # Prefer OAuth2 client-credentials (current OpenSky auth); fall back to
        # deprecated basic auth, then anonymous — each raises the rate ceiling.
        headers = None
        auth = None
        token = await _opensky_token(client)
        if token:
            headers = {"Authorization": f"Bearer {token}"}
        elif settings.opensky_username and settings.opensky_password:
            auth = (settings.opensky_username, settings.opensky_password)
        resp = await client.get(OPENSKY_URL, params=params, auth=auth, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    states = data.get("states") or []
    aircraft = [a for s in states if (a := _normalize(s))]
    return aircraft[:MAX_AIRCRAFT]


@router.get("")
async def get_aircraft(
    lamin: float = Query(-90), lamax: float = Query(90),
    lomin: float = Query(-180), lomax: float = Query(180),
) -> dict:
    """Return live aircraft positions from OpenSky (cached 15s)."""
    global _last_fetch

    key = f"{lamin:.1f},{lamax:.1f},{lomin:.1f},{lomax:.1f}"
    now = time.monotonic()

    cached = _cache.get(key)
    if cached and now - cached[0] < CACHE_TTL:
        return {"aircraft": cached[1], "source": "opensky", "live": True}

    # Throttle across all bboxes to respect OpenSky's rate limit.
    if now - _last_fetch < CACHE_TTL:
        return {"aircraft": cached[1] if cached else [], "source": "opensky", "live": True}

    try:
        aircraft = await _fetch_opensky(lamin, lamax, lomin, lomax)
        _last_fetch = now
        _cache[key] = (now, aircraft)
        return {"aircraft": aircraft, "source": "opensky", "live": True}
    except Exception as exc:  # noqa: BLE001 — degrade gracefully, never 500 the map
        logger.warning("OpenSky fetch failed: %s", exc)
        if cached:
            return {"aircraft": cached[1], "source": "opensky", "live": True}
        return {"aircraft": [], "source": "none", "live": False}
