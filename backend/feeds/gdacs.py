"""
GDACS — Global Disaster Alert & Coordination System. Free, NO key. One GeoJSON
feed covering earthquakes, tropical cyclones, floods, droughts, volcanoes and
wildfires with a Green/Orange/Red alert level.
  https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP

Pure parser (parse_gdacs) → Signal dicts. One integration replaces several
single-hazard feeds, so it slots into hazard_ingest_worker.SOURCES on its own.
"""

FEED_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP"

# GDACS eventtype → (our category, human label).
EVENTTYPE = {
    "EQ": ("disaster", "Earthquake"),
    "TC": ("storm", "Tropical Cyclone"),
    "FL": ("flood", "Flood"),
    "DR": ("drought", "Drought"),
    "VO": ("volcano", "Volcano"),
    "WF": ("wildfire", "Wildfire"),
}
# Alert level → 0–100 importance (mirrors the NWS severe/extreme scale).
ALERT_IMPORTANCE = {"green": 45, "orange": 72, "red": 90}


def _centroid(geometry):
    """[lng, lat] of a GeoJSON Point (or first-ring centroid of a Polygon)."""
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


def parse_gdacs(geojson: dict) -> list[dict]:
    """GDACS FeatureCollection → list of Signal dicts."""
    out = []
    for f in (geojson or {}).get("features", []):
        p = f.get("properties") or {}
        cen = _centroid(f.get("geometry"))
        if not cen:
            continue
        etype = (p.get("eventtype") or "").upper()
        category, label = EVENTTYPE.get(etype, ("disaster", "Hazard"))
        alert = (p.get("alertlevel") or "green").lower()
        imp = ALERT_IMPORTANCE.get(alert, 45)
        name = p.get("name") or p.get("eventname") or label
        country = p.get("country") or ""
        out.append({
            "external_id": f"gdacs-{etype}{p.get('eventid') or p.get('episodeid') or name}",
            "source": "gdacs",
            "title": f"{label} — {name}",
            "summary": p.get("description") or p.get("htmldescription") or f"{label}: {name}. {country}".strip(),
            "category": category,
            "lat": cen[1],
            "lng": cen[0],
            "importance": imp,
            "status": "escalating" if alert in ("orange", "red") else "developing",
            "geography": [g.strip() for g in country.split(",") if g.strip()][:3],
            "ts": None,
        })
    return out


async def fetch_gdacs() -> list[dict]:
    import httpx  # lazy — keeps parse_gdacs importable without the dep
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(FEED_URL)
        resp.raise_for_status()
        return parse_gdacs(resp.json())
