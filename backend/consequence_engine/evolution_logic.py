"""
Pure evolution-pressure logic — no DB. evolution_tracker.py supplies the drift,
new-article volume, staleness, and category, then acts on should_remap().

Replaces the two independent hard gates (drift > 0.15 OR a single ≥80 article)
with one continuous pressure score compared against a threshold that (a) eases as
an event goes stale and (b) is more sensitive for fast-moving categories.
"""

import math

# Per-category threshold multiplier: <1 ⇒ more sensitive (re-maps sooner).
CATEGORY_SENSITIVITY = {
    "conflict": 0.7,
    "geopolitics": 0.8,
    "economics": 0.9,
    "economy": 0.9,
    "technology": 1.1,
    "policy": 1.3,
    "climate": 1.2,
    "health": 1.0,
}
DEFAULT_SENSITIVITY = 1.0


def evolution_pressure(drift: float, n_high_importance: int, volume_weight: float, volume_tau: float) -> float:
    """Combine embedding drift with the volume of new high-importance articles."""
    volume = volume_weight * (1 - math.exp(-max(0, n_high_importance) / volume_tau))
    return max(0.0, drift) + volume


def effective_threshold(base: float, hours_since_map: float | None, category: str | None, staleness_tau: float) -> float:
    """Base threshold scaled by category sensitivity and decayed by staleness."""
    cat_mult = CATEGORY_SENSITIVITY.get((category or "").lower(), DEFAULT_SENSITIVITY)
    staleness = math.exp(-max(0.0, hours_since_map) / staleness_tau) if hours_since_map is not None else 1.0
    return base * cat_mult * staleness


def should_remap(pressure: float, threshold: float) -> bool:
    return pressure >= threshold
