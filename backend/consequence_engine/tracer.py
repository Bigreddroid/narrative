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
            "shared_sectors": ed.get("shared_sectors") or [],
            "shared_geography": ed.get("shared_geography") or [],
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
) -> dict:
    """Forward consequence chain from ``root_id``.

    Returns {root, nodes[], hops[], limited}. ``nodes`` are downstream events ranked
    by the strongest propagated path (score = round(100·Πhop DECAY·weight)); each
    carries its winning ``depth``. ``hops`` is the winning incoming edge per node
    (from, to, weight, depth, shared_sectors, shared_geography, mechanism).
    ``limited`` is True when the root is unknown, isolated, or yields no chain."""
    root_id = str(root_id)
    by_id = {str(e["id"]): e for e in events}
    adj = _adjacency(events, edges)

    def _node(i: str) -> dict:
        e = by_id.get(i) or {}
        return {"id": i, "title": e.get("canonical_title") or e.get("title"),
                "category": e.get("category")}

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
            cand = w_u * DECAY * e["weight"]
            if cand < floor or cand <= 0.0:
                continue  # prune weak tails
            if cand > best.get(v, 0.0):
                best[v] = cand
                best_depth[v] = d + 1
                hop_in[v] = {
                    "from": u,
                    "to": v,
                    "weight": round(e["weight"], 3),
                    "depth": d + 1,
                    "shared_sectors": e["shared_sectors"],
                    "shared_geography": e["shared_geography"],
                    "mechanism": _mechanism(e["shared_sectors"], e["shared_geography"]),
                }
                heapq.heappush(heap, (-cand, d + 1, v))

    reached = [i for i in best if i != root_id]
    nodes = [
        {**_node(i), "depth": best_depth[i], "score": round(100 * best[i])}
        for i in reached
    ]
    nodes.sort(key=lambda n: (-n["score"], n["depth"], str(n["id"])))
    if max_nodes is not None:
        nodes = nodes[:max_nodes]
    keep = {n["id"] for n in nodes}

    hops = [hop_in[i] for i in keep if i in hop_in]
    hops.sort(key=lambda h: (h["depth"], -h["weight"]))

    return {"root": root, "nodes": nodes, "hops": hops, "limited": len(nodes) == 0}
