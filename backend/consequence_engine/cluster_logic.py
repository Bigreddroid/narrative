"""
Pure clustering decision logic — no DB. clusterer.py supplies candidates from
pgvector and applies the decision + centroid update returned here.

Upgrades over a single global cosine threshold:
  • time-decayed similarity — an article far in time from an event is a weaker match
  • hysteresis — a high bar (strong) always attaches; a lower bar attaches only to an
    already-established cluster; otherwise a new event is spawned (reduces fragmentation
    and flip-flopping)
  • running-centroid maintenance — an event's embedding is the mean of its members,
    not frozen to whichever article happened to arrive first
"""

import math


def effective_similarity(sim: float, age_gap_hours: float | None, decay_hours: float) -> float:
    """Cosine similarity discounted by the article↔event time gap."""
    if age_gap_hours is None or decay_hours <= 0:
        return sim
    return sim * math.exp(-max(0.0, age_gap_hours) / decay_hours)


def decide_cluster(
    candidates: list[dict],
    attach_threshold: float,
    strong_threshold: float,
    min_established: int,
    decay_hours: float,
) -> tuple[object | None, float]:
    """Pick the event to attach to (or None ⇒ create new), with the chosen effective sim.

    candidates: dicts with keys {id, sim, age_gap_hours, member_count}.
    """
    best = None
    best_eff = -1.0
    for c in candidates:
        eff = effective_similarity(c["sim"], c.get("age_gap_hours"), decay_hours)
        if eff > best_eff:
            best_eff, best = eff, c

    if best is None:
        return None, 0.0
    if best_eff >= strong_threshold:
        return best["id"], best_eff
    if best_eff >= attach_threshold and best.get("member_count", 0) >= min_established:
        return best["id"], best_eff
    return None, best_eff


def update_centroid(old: list[float], vec: list[float], member_count: int) -> list[float]:
    """Incremental running mean: new centroid after adding `vec` to `member_count` members."""
    if not old:
        return list(vec)
    n = max(0, member_count)
    return [(o * n + v) / (n + 1) for o, v in zip(old, vec)]
