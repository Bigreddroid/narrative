"""
Pure scoring math for event→event connections. No DB / framework imports, so it
is unit-testable in isolation (see graph_scoring_test.py). graph_connector.py
handles the DB orchestration and calls into here.

Upgrade over plain Jaccard: shared tokens are weighted by inverse document
frequency (IDF), so a connection through a rare sector counts far more than one
through a ubiquitous token like "United States". Edges are also directed by time
(the earlier event is the causal source).
"""

import math

# Blend weights across dimensions (sectors dominate, then geography, then keywords).
DIM_WEIGHTS = {"sector": 0.5, "geo": 0.3, "keyword": 0.2}

# Below this embedding cosine, two events sharing a sector/geo tag are treated as a
# coincidence, not a real link (e.g. an unrelated refinery fire and an OPEC statement
# both tagged Energy+US). This gate is what stops the graph from asserting causal
# edges purely from shared tags — the core "linking is inaccurate" problem.
SEMANTIC_FLOOR = 0.30


def build_idf(token_lists: list[list[str]]) -> dict[str, float]:
    """Smoothed IDF over a corpus of per-event token lists for one dimension."""
    n = len(token_lists)
    df: dict[str, int] = {}
    for tokens in token_lists:
        for tok in {t.lower() for t in (tokens or [])}:
            df[tok] = df.get(tok, 0) + 1
    # +1 smoothing keeps a single-doc token finite and ranks rarer tokens higher.
    return {tok: math.log((1 + n) / (1 + d)) + 1 for tok, d in df.items()}


def _default_idf(idf: dict[str, float]) -> float:
    return max(idf.values()) if idf else 1.0


def weighted_overlap(a: list[str] | None, b: list[str] | None, idf: dict[str, float]) -> tuple[float, list[str]]:
    """IDF-weighted overlap ∈ [0,1]: Σ idf(shared) / Σ idf(union)."""
    if not a or not b:
        return 0.0, []
    set_a = {s.lower() for s in a}
    set_b = {s.lower() for s in b}
    shared = set_a & set_b
    if not shared:
        return 0.0, []
    fallback = _default_idf(idf)
    num = sum(idf.get(t, fallback) for t in shared)
    den = sum(idf.get(t, fallback) for t in (set_a | set_b))
    score = num / den if den else 0.0
    return score, sorted(shared)


def blended_weight(sector: float, geo: float, keyword: float) -> float:
    """Weighted blend of the three dimension overlaps."""
    return sector * DIM_WEIGHTS["sector"] + geo * DIM_WEIGHTS["geo"] + keyword * DIM_WEIGHTS["keyword"]


def cosine(a: list[float] | None, b: list[float] | None) -> float | None:
    """Cosine similarity of two event embeddings. None if either is absent (so the
    caller can degrade to tag-only linking); 0.0 for a degenerate/zero vector."""
    if not a or not b or len(a) != len(b):
        return None
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


def semantic_adjust(tag_blend: float, cos: float | None) -> float | None:
    """Refine a tag-overlap weight with embedding cosine similarity.

    - ``cos is None`` (an event lacks an embedding) ⇒ return ``tag_blend`` unchanged
      so we degrade safely to the old tag-only behaviour rather than dropping edges.
    - ``cos`` below :data:`SEMANTIC_FLOOR` ⇒ ``None`` (drop the edge: the events share
      a tag but are about different things — a coincidence, not a causal link).
    - otherwise scale the tag weight by how semantically related the events are, so
      genuinely-related pairs rank above tag-only near-misses. Kept ≥ 0.5·tag_blend
      above the floor so related events aren't over-pruned.
    """
    if cos is None:
        return tag_blend
    if cos < SEMANTIC_FLOOR:
        return None
    factor = (cos - SEMANTIC_FLOOR) / (1.0 - SEMANTIC_FLOOR)  # 0 at floor → 1 at cos=1
    return tag_blend * (0.5 + 0.5 * factor)


def causal_direction(a_time, b_time) -> str | None:
    """Directed edge label relative to stored (a, b): the earlier event is the cause.

    Returns "a_to_b" when a precedes b, "b_to_a" when b precedes a, else None
    (no usable temporal signal ⇒ treat as undirected).
    """
    if a_time is None or b_time is None or a_time == b_time:
        return None
    return "a_to_b" if a_time < b_time else "b_to_a"
