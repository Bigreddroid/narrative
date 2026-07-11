"""
Event-to-event CONSEQUENCE TRACING — pure, deterministic, no DB/LLM.

Given a root event, walk the directed event graph FORWARD to surface how the
event's consequences cascade to other events: a directed, multi-hop, explainable
chain (root → B → C …). Each reached event is scored by the strongest propagated
path to it; each hop carries the mechanism (shared sectors/regions) that links it.

This complements propagation.py: that engine diffuses shock into per-entity
exposure scores; this surfaces the actual event→event paths the diffusion walks,
which propagation collapses into flat drivers and discards. Same per-hop decay
(DECAY == propagation.LAMBDA) so the two stay consistent.

Grounding: a hop is emitted ONLY when a stored edge connects the two events. The
tracer never invents a link — an event with no outgoing edges returns limited=True
and an empty chain rather than a manufactured consequence.
"""

from __future__ import annotations

import heapq

from backend.consequence_engine.propagation import LAMBDA as DECAY  # per-hop causal decay

MECH_COSINE_FLOOR = 0.30  # embedding cosine that makes an edge semantically grounded
# Sectors so ubiquitous that sharing them alone is coincidence, not a consequence link
# (nearly every conflict/disaster event carries these). A hop justified ONLY by these,
# with no shared geography and no embedding, is flagged co-occurrence rather than causal.
GENERIC_SECTORS = {
    "defense", "energy", "commodities", "infrastructure", "shipping",
    "shipping & logistics", "aviation", "technology", "consumer goods",
}


def _classify(meta: dict) -> tuple[str, bool]:
    """Grounding of a hop: (kind, grounded).

    semantic  — edge carries an embedding cosine ≥ floor (events are about the same situation)
    geographic — shares a concrete region
    sectoral  — shares a SPECIFIC (non-ubiquitous) sector
    co_occurrence — only generic shared tags; a weak coincidence, not a consequence link
    """
    cos = meta.get("cosine")
    if cos is not None and cos >= MECH_COSINE_FLOOR:
        return "semantic", True
    if meta.get("shared_geography"):
        return "geographic", True
    if any((s or "").strip().lower() not in GENERIC_SECTORS for s in (meta.get("shared_sectors") or [])):
        return "sectoral", True
    return "co_occurrence", False


def _adjacency(events: list[dict], edges: list[dict]) -> dict[str, list[dict]]:
    """Forward cause→effect adjacency. Undirected edges traverse both ways."""
    ids = {str(e["id"]) for e in events}
    adj: dict[str, list[dict]] = {i: [] for i in ids}
    for ed in edges or []:
        src, tgt = str(ed.get("source")), str(ed.get("target"))
        if src not in ids or tgt not in ids:
            continue  # skip edges to events outside the loaded set
        w = ed.get("weight")
        w = 0.5 if w is None else float(w)
        meta = {
            "weight": w,
            "cosine": ed.get("cosine"),
            "shared_sectors": ed.get("shared_sectors") or [],
            "shared_geography": ed.get("shared_geography") or [],
            # stored directed edge = time-ordered cause→effect (real causal orientation);
            # undirected = symmetric co-occurrence. Carried onto the hop as `directed`.
            "directed": ed.get("directed") is True,
        }
        adj[src].append({"to": tgt, **meta})
        if ed.get("directed") is not True:  # undirected → effect can flow back too
            adj[tgt].append({"to": src, **meta})
    return adj


def _mechanism(shared_sectors: list[str], shared_geography: list[str]) -> str:
    parts = []
    if shared_sectors:
        parts.append("sectors: " + ", ".join(shared_sectors[:3]))
    if shared_geography:
        parts.append("regions: " + ", ".join(shared_geography[:3]))
    return " · ".join(parts) if parts else "related"


def trace_consequences(
    root_id,
    events: list[dict],
    edges: list[dict],
    depth: int = 3,
    floor: float = 0.0,
    max_nodes: int | None = None,
    grounded_only: bool = False,
) -> dict:
    """Forward consequence chain from ``root_id``.

    Returns {root, nodes[], hops[], limited}. ``nodes`` are downstream events ranked
    grounded-first, then by the strongest propagated path (score = round(100·Πhop
    DECAY·weight)); each carries its winning ``depth``, ``kind`` and ``grounded``.
    ``hops`` is the winning incoming edge per node (from, to, weight, depth,
    magnitude, lag_hours, directed, shared_sectors, shared_geography, mechanism,
    kind, grounded). ``magnitude`` is how much the link transmits, ``lag_hours``
    is cause→effect delay (None when a timestamp is missing), ``directed`` marks a
    time-ordered causal edge vs a symmetric co-occurrence. Nodes additionally carry
    ``region``/``lat``/``lng``/``status`` — WHERE the consequence lands.

    Each hop is classified (see _classify): a *grounded* hop is a real consequence
    link (semantic / geographic / specific-sector); a *co_occurrence* hop rests only
    on generic shared tags and is a weak coincidence. ``grounded_only`` drops the
    coincidences entirely. ``limited`` is True when the root is unknown, isolated, or
    yields no (surviving) chain."""
    root_id = str(root_id)
    by_id = {str(e["id"]): e for e in events}
    adj = _adjacency(events, edges)

    def _node(i: str) -> dict:
        e = by_id.get(i) or {}
        geo = e.get("geographic_relevance") or []
        return {
            "id": i,
            "title": e.get("canonical_title") or e.get("title"),
            "category": e.get("category"),
            "status": e.get("current_status") or e.get("status"),
            # WHERE this consequence lands — concrete place + coords when known (R1).
            "region": geo[0] if geo else None,
            "lat": e.get("lat"),
            "lng": e.get("lng"),
        }

    root = _node(root_id) if root_id in by_id else {"id": root_id, "title": None, "category": None}

    # Lazy Dijkstra maximising the path product (equivalently, min sum of -log w).
    # DECAY·w < 1 on every hop, so extra hops strictly weaken a path — the max-product
    # path is well-defined and its hop count is the node's reported depth.
    best: dict[str, float] = {root_id: 1.0}
    best_depth: dict[str, int] = {root_id: 0}
    hop_in: dict[str, dict] = {}
    # heap holds (-reach_weight, depth, node) so the strongest partial path pops first
    heap: list[tuple[float, int, str]] = [(-1.0, 0, root_id)]

    while heap:
        neg_w, d, u = heapq.heappop(heap)
        w_u = -neg_w
        if w_u < best.get(u, 0.0) or d > best_depth.get(u, depth):
            continue  # stale entry superseded by a stronger/shorter path
        if d >= depth:
            continue  # depth cap — do not expand further
        for e in adj.get(u, []):
            v = e["to"]
            if v == root_id:
                continue  # never trace the root back into its own consequences
            kind, grounded = _classify(e)
            if grounded_only and not grounded:
                continue  # drop coincidental (generic-tag) links entirely
            cand = w_u * DECAY * e["weight"]
            if cand < floor or cand <= 0.0:
                continue  # prune weak tails
            if cand > best.get(v, 0.0):
                best[v] = cand
                best_depth[v] = d + 1
                ts_u = (by_id.get(u) or {}).get("ts")
                ts_v = (by_id.get(v) or {}).get("ts")
                # WHEN — hours from cause to effect (positive = effect follows cause).
                lag_hours = (
                    round((ts_v - ts_u) / 3_600_000, 1)
                    if ts_u is not None and ts_v is not None else None
                )
                hop_in[v] = {
                    "from": u,
                    "to": v,
                    "weight": round(e["weight"], 3),
                    "depth": d + 1,
                    # HOW MUCH — strength this single link transmits (0–100).
                    "magnitude": round(100 * DECAY * e["weight"]),
                    "lag_hours": lag_hours,
                    # real causal orientation (time-ordered) vs symmetric co-occurrence.
                    "directed": e.get("directed", False),
                    "shared_sectors": e["shared_sectors"],
                    "shared_geography": e["shared_geography"],
                    "mechanism": _mechanism(e["shared_sectors"], e["shared_geography"]),
                    "kind": kind,
                    "grounded": grounded,
                }
                heapq.heappush(heap, (-cand, d + 1, v))

    reached = [i for i in best if i != root_id]
    nodes = [
        {**_node(i), "depth": best_depth[i], "score": round(100 * best[i]),
         "kind": hop_in[i]["kind"], "grounded": hop_in[i]["grounded"]}
        for i in reached
    ]
    # Grounded consequences rank above weak coincidences, then by path strength.
    nodes.sort(key=lambda n: (not n["grounded"], -n["score"], n["depth"], str(n["id"])))
    if max_nodes is not None:
        nodes = nodes[:max_nodes]
    keep = {n["id"] for n in nodes}

    hops = [hop_in[i] for i in keep if i in hop_in]
    hops.sort(key=lambda h: (not h["grounded"], h["depth"], -h["weight"]))

    return {"root": root, "nodes": nodes, "hops": hops, "limited": len(nodes) == 0}
