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


DEFAULT_MAX_TIME_PENALTY = 0.05


def effective_similarity(
    sim: float,
    age_gap_hours: float | None,
    decay_hours: float,
    max_time_penalty: float = DEFAULT_MAX_TIME_PENALTY,
) -> float:
    """Cosine similarity with a BOUNDED time penalty.

    This used to be `sim * exp(-gap/decay)`. Because the attach/strong bars are
    fixed constants and cosine cannot exceed 1.0, multiplying by a decay term put a
    hard mathematical ceiling on how old a match could be — regardless of how
    identical the two articles were:

        need  sim * exp(-t/decay) >= bar,  sim <= 1.0
        =>    t <= -decay * ln(bar)

    At the shipped settings (decay 7d = 168h, strong 0.84, attach 0.80) that is
    **29.3h** to gain a second member and **37.5h** to attach at all. Past 37.5h an
    exact duplicate scored 1.0 still spawned a new event. Since a fresh event has
    one member and `min_established` is 2, an event that missed its ~29h window
    could never become established, so it could never attach anything again — the
    fragmentation was self-locking. Measured on the live corpus before this fix:
    mean 1.10 articles/event, 94% of events single-article, only 5.9% with >=2
    distinct outlets.

    The penalty now saturates at `max_time_penalty`, so age can order and
    discourage candidates but can never veto a semantically identical one. The
    hard time gate stays where it belongs: the candidate query's
    `cluster_time_window_days`.
    """
    if age_gap_hours is None or decay_hours <= 0:
        return sim
    gap = max(0.0, age_gap_hours)
    return sim - max_time_penalty * (1.0 - math.exp(-gap / decay_hours))


def decide_cluster(
    candidates: list[dict],
    attach_threshold: float,
    strong_threshold: float,
    min_established: int,
    decay_hours: float,
    max_time_penalty: float = DEFAULT_MAX_TIME_PENALTY,
) -> tuple[object | None, float]:
    """Pick the event to attach to (or None ⇒ create new), with the chosen effective sim.

    candidates: dicts with keys {id, sim, age_gap_hours, member_count}.
    """
    best = None
    best_eff = -1.0
    for c in candidates:
        eff = effective_similarity(c["sim"], c.get("age_gap_hours"), decay_hours, max_time_penalty)
        if eff > best_eff:
            best_eff, best = eff, c

    if best is None:
        return None, 0.0
    if best_eff >= strong_threshold:
        return best["id"], best_eff
    if best_eff >= attach_threshold and best.get("member_count", 0) >= min_established:
        return best["id"], best_eff
    return None, best_eff


def update_centroid(old, vec, member_count: int) -> list[float]:
    """Incremental running mean: new centroid after adding `vec` to `member_count` members.

    `old` arrives from pgvector as a numpy ndarray, not a list. A bare `if not old`
    raises ValueError("truth value of an array ... is ambiguous") on any real embedding,
    which crashed cluster_worker on every run from 2026-07-13 onward and left all 28k
    collected articles unattached to their events — so no event had a source, no
    corroboration count could be computed, and the two-source gate could never pass.
    Test emptiness by length, never by truthiness, for anything array-shaped.
    """
    if old is None or len(old) == 0:
        return list(vec)
    n = max(0, member_count)
    return [(o * n + v) / (n + 1) for o, v in zip(old, vec)]
