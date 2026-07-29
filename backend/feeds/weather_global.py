"""
Global severe weather — free, NO key (Open-Meteo).
  • https://api.open-meteo.com/v1/forecast — daily precipitation / max temp / max
    wind gust for a set of monitored points, queried in a single multi-coordinate call.

The existing `weather.py` covers only the US (NWS alerts) + Atlantic hurricanes (NHC),
so a footprint centred on India/GCC/Europe gets no weather signal at all. This feed
watches a set of points (seeded from real corporate-security office coordinates) and
emits a Signal dict only when the next-day forecast crosses a disruptive threshold —
heavy rain / monsoon, extreme heat, or damaging wind gusts. Pure parser
(`parse_openmeteo`) → Signal dicts (category "storm"), same shape as `weather.py`.
"""

import logging

logger = logging.getLogger(__name__)

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
DAILY = "precipitation_sum,temperature_2m_max,wind_gusts_10m_max"

# SEED points only — the fallback used when the register cannot be read. This list was
# the entire weather footprint until it was measured against the live register: 92 of
# 134 registered sites (69%) had NO monitored point within the 150 km storm-association
# radius, the farthest being 9,116 km from one, while the deck's all-layers strip
# reported weather as "of 121" — i.e. claimed to have checked every site. That is the
# same lie the FESTIVAL tile was fixed for. monitored_points() below derives the real
# list from the sites table; this remains only so a DB-less run still watches something
# rather than silently watching nothing.
SEED_POINTS = [
    {"name": "Bengaluru", "lat": 12.95, "lng": 77.66},
    {"name": "Hyderabad", "lat": 17.44, "lng": 78.35},
    {"name": "Pune", "lat": 18.59, "lng": 73.74},
    {"name": "Chennai", "lat": 12.90, "lng": 80.23},
    {"name": "Kochi", "lat": 10.01, "lng": 76.36},
    {"name": "Delhi NCR", "lat": 28.47, "lng": 77.50},
    {"name": "Mumbai", "lat": 19.12, "lng": 72.90},
    {"name": "East Brunswick", "lat": 40.43, "lng": -74.42},
    {"name": "London", "lat": 51.51, "lng": -0.10},
    {"name": "Frankfurt", "lat": 50.11, "lng": 8.68},
    {"name": "Bucharest", "lat": 44.44, "lng": 26.10},
    {"name": "Dubai", "lat": 25.10, "lng": 55.16},
    {"name": "Riyadh", "lat": 24.71, "lng": 46.68},
]

# (threshold, importance, label) tiers, worst-first. A point emits the single worst
# condition it triggers — keeps one clean marker per city instead of three stacked ones.
RAIN_TIERS = [(100.0, 84, "Very heavy rainfall"), (50.0, 68, "Heavy rainfall")]      # mm/day
HEAT_TIERS = [(45.0, 82, "Extreme heat"), (42.0, 70, "Severe heat"), (40.0, 56, "Heat")]  # °C
WIND_TIERS = [(90.0, 80, "Damaging winds"), (70.0, 66, "Strong winds"), (60.0, 55, "High winds")]  # km/h


def _worst(value, tiers):
    """First (importance, label) whose threshold `value` meets, else None."""
    if value is None:
        return None
    for thresh, imp, label in tiers:
        if value >= thresh:
            return imp, label
    return None


def parse_openmeteo(payload, points: list[dict]) -> list[dict]:
    """Map Open-Meteo daily forecast(s) → Signal dicts, one per point that crosses a
    disruptive threshold. `payload` is a single forecast object (one point) or a list
    (multi-coordinate response); `points` is the parallel slice of monitored points."""
    blocks = payload if isinstance(payload, list) else [payload]
    out = []
    for i, block in enumerate(blocks):
        if i >= len(points):
            break
        pt = points[i]
        daily = (block or {}).get("daily") or {}
        times = daily.get("time") or []
        if not times:
            continue
        rain = (daily.get("precipitation_sum") or [None])[0]
        temp = (daily.get("temperature_2m_max") or [None])[0]
        wind = (daily.get("wind_gusts_10m_max") or [None])[0]
        day = times[0]

        candidates = []
        r = _worst(rain, RAIN_TIERS)
        if r:
            candidates.append((r[0], f"{r[1]} — {pt['name']}", f"Forecast {rain:.0f} mm precipitation"))
        h = _worst(temp, HEAT_TIERS)
        if h:
            candidates.append((h[0], f"{h[1]} — {pt['name']}", f"Forecast max {temp:.0f}°C"))
        w = _worst(wind, WIND_TIERS)
        if w:
            candidates.append((w[0], f"{w[1]} — {pt['name']}", f"Forecast gusts to {wind:.0f} km/h"))
        if not candidates:
            continue
        imp, title, summary = max(candidates, key=lambda c: c[0])
        out.append({
            "external_id": f"openmeteo-{pt['name'].lower().replace(' ', '-')}-{day}",
            "source": "open-meteo",
            "title": title,
            "summary": f"{summary} near {pt['name']} on {day} (Open-Meteo).",
            "category": "storm",
            "lat": pt["lat"],
            "lng": pt["lng"],
            "importance": imp,
            "status": "escalating" if imp >= 70 else "developing",
            "geography": [pt["name"]],
            "ts": None,
        })
    return out


def collapse_points(rows, precision: float = 0.5) -> list[dict]:
    """Site coordinates -> one weather point per metro.

    Campuses in the same city share weather, so querying each of them separately buys
    nothing and multiplies the request. Rounding to `precision` degrees (~55 km at the
    equator) folds a metro into a single point while keeping distinct cities apart.
    """
    seen: dict[tuple[float, float], dict] = {}
    for name, lat, lng in rows:
        if lat is None or lng is None:
            continue
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            continue
        key = (round(lat / precision) * precision, round(lng / precision) * precision)
        seen.setdefault(key, {"name": name or "site", "lat": round(lat, 3), "lng": round(lng, 3)})
    return list(seen.values())


async def monitored_points() -> list[dict]:
    """The points to watch: the live register, collapsed to metros.

    Falls back to SEED_POINTS only when the register cannot be read at all — never to
    an empty list, because "no points" would render as "no severe weather anywhere"
    rather than as "we did not check".
    """
    try:
        from sqlalchemy import text

        from backend.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(text(
                "SELECT city, lat, lng FROM sites "
                "WHERE lat IS NOT NULL AND lng IS NOT NULL AND is_active"
            ))).all()
        pts = collapse_points([(r[0], r[1], r[2]) for r in rows])
        if pts:
            return pts
        logger.warning("weather_global: register held no usable coordinates; using seed points")
    except Exception as exc:  # noqa: BLE001 — the feed must still run without a DB
        logger.warning("weather_global: could not read the register (%s: %s); using seed points",
                       type(exc).__name__, exc)
    return SEED_POINTS


# Open-Meteo takes many coordinates per call, but not unboundedly — chunk so a large
# register does not produce one enormous URL that the API rejects wholesale.
_CHUNK = 50


async def fetch_weather_global() -> list[dict]:
    import httpx  # lazy — keeps the parser importable without the dep

    points = await monitored_points()
    out: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for i in range(0, len(points), _CHUNK):
                batch = points[i:i + _CHUNK]
                params = {
                    "latitude": ",".join(f"{p['lat']}" for p in batch),
                    "longitude": ",".join(f"{p['lng']}" for p in batch),
                    "daily": DAILY, "forecast_days": 1, "timezone": "auto",
                }
                r = await client.get(OPEN_METEO, params=params)
                if r.status_code == 200:
                    out.extend(parse_openmeteo(r.json(), batch))
                else:
                    logger.warning("weather_global: Open-Meteo returned %s for %d points",
                                   r.status_code, len(batch))
    except Exception as exc:  # noqa: BLE001 — one bad feed must not sink the ingest run
        logger.warning("weather_global: fetch failed (%s: %s)", type(exc).__name__, exc)
    return out
