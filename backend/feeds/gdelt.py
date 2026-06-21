"""
GDELT GEO 2.0 — free, NO key. Geocoded global news-activity hotspots updated
every 15 min. We query conflict/unrest themes and treat each returned location
as a rolling hotspot event whose importance scales with mention volume.
  https://api.gdeltproject.org/api/v2/geo/geo?query=...&format=GeoJSON

GeoJSON features carry geometry Point [lng, lat] + properties {name, count, html}.
There is no per-feature tone in the GEO API, so importance is volume-driven.
"""

# GEO API query — conflict/unrest themes. Tunable.
DEFAULT_QUERY = "(protest OR unrest OR clash OR conflict OR airstrike OR militants)"
FEED_URL = "https://api.gdeltproject.org/api/v2/geo/geo"


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def importance_from_count(count: float) -> int:
    """Mention volume → 0–100 importance. count 1≈37, 20≈65, ≥40 caps near 95."""
    return int(_clamp(round(35 + (count or 0) * 1.5), 35, 95))


def _slug(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in (name or "")).strip("-")[:60]


def _centroid(geometry):
    if not geometry:
        return None
    t, c = geometry.get("type"), geometry.get("coordinates")
    if t == "Point" and c and len(c) >= 2:
        return (c[0], c[1])
    if t == "Polygon" and c and c[0]:
        ring = c[0]
        n = len(ring)
        if n:
            return (sum(p[0] for p in ring) / n, sum(p[1] for p in ring) / n)
    return None


def parse_gdelt(geojson: dict) -> list[dict]:
    """GDELT GEO FeatureCollection → list of Signal dicts (category 'conflict')."""
    out = []
    for f in (geojson or {}).get("features", []):
        p = f.get("properties") or {}
        cen = _centroid(f.get("geometry"))
        if not cen:
            continue
        name = p.get("name") or "Unknown location"
        try:
            count = float(p.get("count") or 0)
        except (TypeError, ValueError):
            count = 0.0
        imp = importance_from_count(count)
        out.append({
            "external_id": f"gdelt-{_slug(name)}",
            "source": "gdelt",
            "title": f"News-activity spike — {name}",
            "summary": f"{int(count)} geocoded reports of conflict/unrest activity near {name} (GDELT, 24h).",
            "category": "conflict",
            "lat": cen[1],
            "lng": cen[0],
            "importance": imp,
            "status": "escalating" if imp >= 70 else "developing",
            "geography": [name],
            "ts": None,
        })
    return out


async def fetch_gdelt(query: str = DEFAULT_QUERY) -> list[dict]:
    import httpx  # lazy — keeps parse_gdelt importable without the dep
    params = {"query": query, "format": "GeoJSON", "mode": "PointData", "timespan": "24h"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(FEED_URL, params=params)
        resp.raise_for_status()
        return parse_gdelt(resp.json())
