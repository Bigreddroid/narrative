"""
Chokepoint Congestion Index — derived IP, NO new data dependency. Computes vessel
congestion at the world's strategic maritime chokepoints from AIS positions the
platform already ingests, and projects it as Shipping/Energy sector stress for the
CPE (same {sector: 0-1} shape as market.sector_stress).

Pure functions only (haversine, congestion_from_count, chokepoint_congestion,
sector_stress) — fully unit-testable, no I/O. Tuned constants are the secret sauce.
"""

import math

# name → (lat, lng, radius_km, is_oil_route)
CHOKEPOINTS = {
    "Strait of Hormuz":  (26.57, 56.25, 80, True),
    "Suez Canal":        (30.00, 32.55, 60, True),
    "Bab-el-Mandeb":     (12.60, 43.40, 70, True),
    "Strait of Malacca": (1.80, 102.50, 120, False),
    "Panama Canal":      (9.10, -79.70, 50, False),
    "Bosphorus":         (41.10, 29.05, 30, False),
}

TAU_VESSELS = 40.0  # vessel count giving ~0.63 congestion (saturation). Tunable.


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def congestion_from_count(n: float) -> float:
    """Saturating 0–1 congestion from vessel count in a chokepoint zone."""
    return round(1 - math.exp(-(n or 0) / TAU_VESSELS), 4)


def chokepoint_congestion(vessels: list[dict]) -> list[dict]:
    """AIS vessels (each {lat, lng, ...}) → per-chokepoint congestion records."""
    out = []
    for name, (lat, lng, radius, is_oil) in CHOKEPOINTS.items():
        count = 0
        for v in vessels or []:
            vlat, vlng = v.get("lat"), v.get("lng")
            if vlat is None or vlng is None:
                continue
            if haversine_km(lat, lng, vlat, vlng) <= radius:
                count += 1
        out.append({
            "name": name, "lat": lat, "lng": lng, "is_oil": is_oil,
            "count": count, "congestion": congestion_from_count(count),
        })
    return out


def sector_stress(congestion: list[dict]) -> dict:
    """Per-sector 0–1 stress from chokepoint congestion — feeds the CPE market term.

    Shipping & Logistics tracks the worst congestion anywhere; Energy tracks the
    worst congestion on an oil route only.
    """
    if not congestion:
        return {}
    ship = max((c["congestion"] for c in congestion), default=0.0)
    oil = max((c["congestion"] for c in congestion if c.get("is_oil")), default=0.0)
    stress = {}
    if ship > 0:
        stress["Shipping & Logistics"] = ship
    if oil > 0:
        stress["Energy"] = oil
    return stress
