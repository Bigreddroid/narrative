"""
NOAA SWPC space weather — free, NO key. Planetary K-index → geomagnetic-storm
(G-scale) stress projected onto space-exposed sectors. Modelled as sector stress
(like market.sector_stress), NOT a point event, since a geomagnetic storm is global.
  https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json

Pure: parse_kp, kp_to_gscale, sector_stress. fetch_kp() does the I/O.

NOTE: CPE wiring (merging this into the exposure market_stress term in
backend/api/routes/exposure.py) is the follow-up step — see roadmap.
"""

# Sector → sensitivity weight to a geomagnetic storm. Tunable.
SWPC_SECTORS = {
    "Aerospace": 1.0,          # satellites: drag, SEUs, comms loss
    "Telecommunications": 0.9,  # GPS/GNSS + HF radio degradation
    "Aviation": 0.7,            # polar routes reroute, HF comms
    "Infrastructure": 0.6,      # power-grid GICs at high latitude
}


def _clamp01(x):
    return max(0.0, min(1.0, x))


def parse_kp(data: list) -> float | None:
    """Latest Kp from SWPC planetary-K JSON. Handles both real shapes:
    list-of-dicts ([{"time_tag":…, "Kp": 3.33}, …]) and the legacy
    header-row + list-rows form ([["time_tag","Kp",…], ["…","3.00",…], …])."""
    if not data:
        return None
    rows = list(data)
    # Real /products/noaa-planetary-k-index.json: list of dicts, newest last.
    if isinstance(rows[0], dict):
        for row in reversed(rows):
            for key in ("Kp", "kp_index", "kp", "estimated_kp"):
                if row.get(key) is not None:
                    try:
                        return float(row[key])
                    except (TypeError, ValueError):
                        break
        return None
    # Legacy list-of-lists with a header row.
    if len(rows) < 2:
        return None
    header = rows[0]
    kp_idx = header.index("Kp") if isinstance(header, list) and "Kp" in header else 1
    for row in reversed(rows[1:]):
        try:
            return float(row[kp_idx])
        except (TypeError, ValueError, IndexError):
            continue
    return None


def kp_to_gscale(kp: float | None) -> str:
    """Kp → NOAA G-scale. Kp<5 ⇒ G0 (no storm), 5→G1 … 9→G5."""
    if kp is None or kp < 5:
        return "G0"
    return f"G{int(min(5, kp - 4))}"


def sector_stress(kp: float | None) -> dict:
    """Latest Kp → {sector: 0-1} stress. Only geomagnetic storms (Kp≥5) register."""
    if kp is None:
        return {}
    base = _clamp01((kp - 4) / 5.0)  # Kp5→0.2 (G1) … Kp9→1.0 (G5); <5 ⇒ 0
    if base <= 0:
        return {}
    return {s: round(base * w, 4) for s, w in SWPC_SECTORS.items() if base * w > 0}


async def fetch_kp() -> float | None:
    import httpx  # lazy — keeps parsers importable without the dep
    url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return parse_kp(resp.json())


# TTL cache so the request path (exposure route) hits SWPC at most once per window.
KP_TTL = 900.0  # seconds (Kp updates every ~3h; 15 min cache is ample)
_kp_cache = {"ts": 0.0, "value": None}


async def latest_kp(ttl: float = KP_TTL) -> float | None:
    """Cached latest Kp. Serves the cached value within `ttl`; on fetch failure
    returns the last known value (stale-tolerant) so /exposure never breaks."""
    import time
    now = time.monotonic()
    if _kp_cache["value"] is not None and now - _kp_cache["ts"] < ttl:
        return _kp_cache["value"]
    try:
        kp = await fetch_kp()
    except Exception:  # noqa: BLE001 — degrade to last-known, never raise into the request
        return _kp_cache["value"]
    _kp_cache["ts"] = now
    _kp_cache["value"] = kp
    return kp
