"""
USGS Earthquakes — free, NO key. GeoJSON summary feed.
https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/
"""

FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def importance_from_magnitude(mag: float) -> int:
    """Magnitude → 0–100 importance. M4.5≈54, M6≈72, M7≈84, M8≈96."""
    return int(_clamp(round((mag or 0) * 12), 0, 100))


def _region(place: str) -> list[str]:
    # USGS place is like "12km SSW of Town, Country" → take the part after "of".
    if not place:
        return []
    tail = place.split(" of ")[-1] if " of " in place else place
    return [p.strip() for p in tail.split(",") if p.strip()][:3]


def parse_earthquakes(geojson: dict) -> list[dict]:
    """USGS FeatureCollection → list of Signal dicts."""
    out = []
    for f in (geojson or {}).get("features", []):
        props = f.get("properties") or {}
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates") or []
        mag = props.get("mag")
        if mag is None or len(coords) < 2:
            continue
        lng, lat = coords[0], coords[1]
        place = props.get("place") or "Unknown location"
        imp = importance_from_magnitude(mag)
        out.append({
            "external_id": f.get("id"),
            "source": "usgs",
            "title": f"M{mag} earthquake — {place}",
            "summary": f"Magnitude {mag} earthquake at depth {coords[2] if len(coords) > 2 else '?'} km, {place}.",
            "category": "disaster",
            "lat": lat,
            "lng": lng,
            "importance": imp,
            "status": "escalating" if mag >= 6 else "developing",
            "geography": _region(place),
            "ts": props.get("time"),
        })
    return out


async def fetch_earthquakes() -> list[dict]:
    import httpx  # lazy — keeps parse_earthquakes importable without the dep
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(FEED_URL)
        resp.raise_for_status()
        return parse_earthquakes(resp.json())
