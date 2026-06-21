"""
THE NARRATIVE — CROSS-FEED CORROBORATION — server-side engine IP.

A consequence reported by several *independent* feeds converging on the same place
and time is more real than one source alone. This turns multi-feed convergence into
a bounded, attributable corroboration index per event — deterministic, explainable,
no LLM. Defensible IP: a single-source competitor cannot reproduce convergence
across an independent feed set (USGS, GDACS, GDELT, weather, launches, market, AIS).

For event e, let S(e) = distinct *other* sources with an event inside e's spatial
radius and time window:

    index(e) = 1 − e^(−|S(e)| / KAPPA_SOURCES)                       (bounded 0–1)
    boost(importance) = importance · (1 + CORROB_W · index)         (≤ importance·(1+CORROB_W))

Tuned constants are the secret sauce — server-side only.
"""

from __future__ import annotations

import math

# Tuned "secret sauce" — versioned with the model. SERVER-SIDE ONLY.
KAPPA_SOURCES = 2.0       # distinct-source saturation (2 independent sources ≈ 0.63)
DEFAULT_RADIUS_KM = 400.0  # spatial proximity for "same place"
DEFAULT_WINDOW_HOURS = 72.0  # temporal proximity for "same time"
CORROB_W = 0.4            # max importance uplift from full corroboration (+40%)


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def corroborate(events: list[dict], radius_km: float = DEFAULT_RADIUS_KM,
                window_hours: float = DEFAULT_WINDOW_HOURS) -> dict:
    """Map event id → {index, count, sources} from independent feed convergence.

    Each event needs {id, source, lat, lng, ts} (ts = epoch ms). Events missing
    coordinates, source or ts cannot be geo/time-corroborated and get index 0.
    Only sources DIFFERENT from the event's own count — repeated reports from the
    same feed are not independent corroboration.
    """
    window_ms = window_hours * 3600_000.0
    out: dict = {}
    for e in events:
        eid = e.get("id")
        if eid is None:
            continue
        lat, lng, ts, src = e.get("lat"), e.get("lng"), e.get("ts"), e.get("source")
        if lat is None or lng is None or ts is None:
            out[eid] = {"index": 0.0, "count": 0, "sources": []}
            continue
        corroborating: set = set()
        for o in events:
            if o is e or o.get("id") == eid:
                continue
            osrc = o.get("source")
            if not osrc or osrc == src:
                continue
            olat, olng, ots = o.get("lat"), o.get("lng"), o.get("ts")
            if olat is None or olng is None or ots is None:
                continue
            if abs(ots - ts) > window_ms:
                continue
            if _haversine_km(lat, lng, olat, olng) <= radius_km:
                corroborating.add(osrc)
        n = len(corroborating)
        idx = round(1 - math.exp(-n / KAPPA_SOURCES), 4) if n else 0.0
        out[eid] = {"index": idx, "count": n, "sources": sorted(corroborating)}
    return out


def corroboration_boost(importance: float, index: float) -> float:
    """Importance uplifted by its corroboration index (bounded by CORROB_W)."""
    return round((importance or 0) * (1 + CORROB_W * max(0.0, min(1.0, index))), 2)
