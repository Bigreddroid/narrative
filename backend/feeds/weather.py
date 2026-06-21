"""
Weather / storms & cyclones — free, NO key.
  • NWS active alerts — https://api.weather.gov/alerts/active (requires a User-Agent)
  • NHC active tropical cyclones — https://www.nhc.noaa.gov/CurrentStorms.json

Pure parsers (parse_nws_alerts, parse_nhc_storms) → Signal dicts (category "storm").
NWS alerts without geometry are skipped (no point to place on the globe).
"""

NWS_ALERTS = "https://api.weather.gov/alerts/active?status=actual&message_type=alert&severity=Severe,Extreme"
NHC_STORMS = "https://www.nhc.noaa.gov/CurrentStorms.json"

NWS_SEVERITY_IMPORTANCE = {"extreme": 88, "severe": 72, "moderate": 55, "minor": 40, "unknown": 45}
# NHC classification → importance. MH=major hurricane, HU=hurricane, TS=tropical storm, TD=depression.
NHC_CLASS_IMPORTANCE = {"MH": 95, "HU": 90, "STS": 78, "TS": 70, "SS": 60, "TD": 55, "SD": 52, "PTC": 50}


def _centroid(geometry):
    """[lng, lat] centroid of a GeoJSON Point or Polygon (or None)."""
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


def parse_nws_alerts(geojson: dict) -> list[dict]:
    out = []
    for f in (geojson or {}).get("features", []):
        p = f.get("properties") or {}
        cen = _centroid(f.get("geometry"))
        if not cen:
            continue
        sev = (p.get("severity") or "unknown").lower()
        event = p.get("event") or "Weather alert"
        area = p.get("areaDesc") or ""
        out.append({
            "external_id": p.get("id") or f.get("id"),
            "source": "nws",
            "title": f"{event} — {area[:60]}" if area else event,
            "summary": p.get("headline") or event,
            "category": "storm",
            "lat": cen[1],
            "lng": cen[0],
            "importance": NWS_SEVERITY_IMPORTANCE.get(sev, 45),
            "status": "escalating" if sev in ("extreme", "severe") else "developing",
            "geography": [a.strip() for a in area.split(";")[:3] if a.strip()],
            "ts": None,
        })
    return out


def parse_nhc_storms(data: dict) -> list[dict]:
    out = []
    for s in (data or {}).get("activeStorms", []):
        lat, lng = s.get("latitudeNumeric"), s.get("longitudeNumeric")
        if lat is None or lng is None:
            continue
        cls = (s.get("classification") or "").upper()
        imp = NHC_CLASS_IMPORTANCE.get(cls, 65)
        name = s.get("name") or "Tropical system"
        out.append({
            "external_id": s.get("id") or f"nhc-{name}",
            "source": "nhc",
            "title": f"{s.get('classification') or 'Storm'} {name}",
            "summary": f"{name}: {s.get('classification') or 'tropical system'}, "
                       f"{s.get('intensity') or '?'} kt winds, moving {s.get('movementDir') or '?'}.",
            "category": "storm",
            "lat": lat,
            "lng": lng,
            "importance": imp,
            "status": "escalating" if imp >= 70 else "developing",
            "geography": [s.get("tcType") or "ocean basin"],
            "ts": None,
        })
    return out


async def fetch_weather() -> list[dict]:
    import httpx  # lazy — keeps parsers importable without the dep
    out = []
    headers = {"User-Agent": "the-narrative/1.0 (intelligence@narrative.app)"}  # NWS requires a UA
    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        try:
            r = await client.get(NWS_ALERTS)
            if r.status_code == 200:
                out.extend(parse_nws_alerts(r.json()))
        except Exception:  # noqa: BLE001
            pass
        try:
            r = await client.get(NHC_STORMS)
            if r.status_code == 200:
                out.extend(parse_nhc_storms(r.json()))
        except Exception:  # noqa: BLE001
            pass
    return out
