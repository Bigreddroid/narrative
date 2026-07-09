"""Property tests for the consequence tracer (pure, no DB/LLM). Run from repo root:
    python -m backend.consequence_engine.tracer_test
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.consequence_engine.tracer import DECAY, trace_consequences

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


def ev(i, cat="conflict"):
    return {"id": i, "title": f"Event {i}", "category": cat}


def edge(a, b, w=0.8, directed=True, **extra):
    return {"source": a, "target": b, "weight": w, "directed": directed, **extra}


EVENTS = [ev("A"), ev("B"), ev("C"), ev("D")]

# ── direct consequence ───────────────────────────────────────────────────────
t = trace_consequences("A", EVENTS, [edge("A", "B", 0.9)])
node_ids = {n["id"] for n in t["nodes"]}
ok("direct: B is a downstream node", "B" in node_ids)
ok("direct: root not listed as its own consequence", "A" not in node_ids)
ok("direct: one hop A→B", any(h["from"] == "A" and h["to"] == "B" for h in t["hops"]))
b = next(n for n in t["nodes"] if n["id"] == "B")
ok("direct: B at depth 1", b["depth"] == 1)
ok("direct: B score = round(100·DECAY·0.9)", b["score"] == round(100 * DECAY * 0.9))
ok("direct: not limited when edges exist", t["limited"] is False)
ok("direct: root echoed back", t["root"]["id"] == "A")

# ── multi-hop decay ──────────────────────────────────────────────────────────
t = trace_consequences("A", EVENTS, [edge("A", "B", 0.9), edge("B", "C", 0.8)])
ids = {n["id"] for n in t["nodes"]}
ok("multihop: C reachable at depth 2", any(n["id"] == "C" and n["depth"] == 2 for n in t["nodes"]))
sb = next(n["score"] for n in t["nodes"] if n["id"] == "B")
sc = next(n["score"] for n in t["nodes"] if n["id"] == "C")
ok("multihop: deeper node decays (score C < score B)", sc < sb)

# ── depth cap ────────────────────────────────────────────────────────────────
t = trace_consequences("A", EVENTS, [edge("A", "B", 0.9), edge("B", "C", 0.8)], depth=1)
ok("depth cap: C excluded at depth=1", all(n["id"] != "C" for n in t["nodes"]))
ok("depth cap: B still present", any(n["id"] == "B" for n in t["nodes"]))

# ── direction respected ──────────────────────────────────────────────────────
# Only edge is B→A (directed). Tracing consequences OF A must find nothing.
t = trace_consequences("A", EVENTS, [edge("B", "A", 0.9, directed=True)])
ok("direction: directed B→A gives A no downstream", t["nodes"] == [])
ok("direction: isolated root is limited", t["limited"] is True)

# ── undirected traverses both ways ───────────────────────────────────────────
t = trace_consequences("A", EVENTS, [edge("B", "A", 0.9, directed=False)])
ok("undirected: A reaches B via undirected edge", any(n["id"] == "B" for n in t["nodes"]))

# ── cycle safety ─────────────────────────────────────────────────────────────
t = trace_consequences("A", EVENTS, [edge("A", "B", 0.9), edge("B", "A", 0.9)])
ok("cycle: terminates", True)  # reaching here means no infinite loop
ok("cycle: A never becomes its own consequence", all(n["id"] != "A" for n in t["nodes"]))

# ── ranking by strength ──────────────────────────────────────────────────────
t = trace_consequences("A", EVENTS, [edge("A", "B", 0.9), edge("A", "C", 0.3)])
order = [n["id"] for n in t["nodes"]]
ok("ranking: stronger consequence first (B before C)", order.index("B") < order.index("C"))

# ── strongest path wins when two routes reach a node ─────────────────────────
t = trace_consequences(
    "A", EVENTS,
    [edge("A", "D", 0.2), edge("A", "B", 0.9), edge("B", "D", 0.9)],
)
d = next(n for n in t["nodes"] if n["id"] == "D")
# direct A→D = DECAY·0.2 = 0.10; via B = DECAY·0.9·DECAY·0.9 = 0.2025 → stronger path kept
ok("strongest-path: D takes the stronger 2-hop route", d["score"] == round(100 * (DECAY * 0.9) * (DECAY * 0.9)))
ok("strongest-path: D depth reflects winning route (2)", d["depth"] == 2)

# ── honest empty ─────────────────────────────────────────────────────────────
t = trace_consequences("A", EVENTS, [])
ok("empty: no edges → no nodes", t["nodes"] == [])
ok("empty: no edges → limited", t["limited"] is True)
ok("empty: unknown root → limited, no crash", trace_consequences("Z", EVENTS, [edge("A", "B")])["limited"] is True)

# ── mechanism carried on hops ────────────────────────────────────────────────
t = trace_consequences(
    "A", EVENTS,
    [edge("A", "B", 0.8, shared_sectors=["energy"], shared_geography=["Strait of Hormuz"])],
)
h = t["hops"][0]
ok("mechanism: shared_sectors carried on hop", h.get("shared_sectors") == ["energy"])
ok("mechanism: shared_geography carried on hop", h.get("shared_geography") == ["Strait of Hormuz"])
ok("mechanism: label mentions the linking sector", "energy" in (h.get("mechanism") or "").lower())

# ── floor prunes weak tails ──────────────────────────────────────────────────
t = trace_consequences("A", EVENTS, [edge("A", "B", 0.9), edge("B", "C", 0.05)], floor=0.10)
ok("floor: weak deep hop pruned (C dropped)", all(n["id"] != "C" for n in t["nodes"]))
ok("floor: above-floor node kept (B present)", any(n["id"] == "B" for n in t["nodes"]))

# ── hop grounding classification (Phase 2) ───────────────────────────────────
# semantic: edge carries an embedding cosine above the floor
t = trace_consequences("A", EVENTS, [edge("A", "B", 0.8, cosine=0.55)])
h = t["hops"][0]
ok("kind: cosine ≥ floor → semantic + grounded", h["kind"] == "semantic" and h["grounded"] is True)

# geographic: no cosine but a shared region
t = trace_consequences("A", EVENTS, [edge("A", "B", 0.8, shared_geography=["Strait of Hormuz"])])
h = t["hops"][0]
ok("kind: shared geography → geographic + grounded", h["kind"] == "geographic" and h["grounded"] is True)

# sectoral: a SPECIFIC (non-ubiquitous) shared sector
t = trace_consequences("A", EVENTS, [edge("A", "B", 0.8, shared_sectors=["semiconductors"])])
h = t["hops"][0]
ok("kind: specific sector → sectoral + grounded", h["kind"] == "sectoral" and h["grounded"] is True)

# co-occurrence: only generic sectors, no geo, no cosine → weak coincidence
t = trace_consequences("A", EVENTS, [edge("A", "B", 0.8, shared_sectors=["defense", "energy"])])
h = t["hops"][0]
ok("kind: generic-sector only → co_occurrence + not grounded",
   h["kind"] == "co_occurrence" and h["grounded"] is False)
ok("kind: co-occurrence node carries grounded=False", t["nodes"][0]["grounded"] is False)

# grounded ranks above a stronger co-occurrence
t = trace_consequences(
    "A", EVENTS,
    [edge("A", "B", 0.4, shared_geography=["Gulf"]), edge("A", "C", 0.95)],  # C stronger but coincidental
)
order = [n["id"] for n in t["nodes"]]
ok("ranking: grounded hop outranks a stronger coincidence", order.index("B") < order.index("C"))

# grounded_only drops coincidental hops
t = trace_consequences(
    "A", EVENTS,
    [edge("A", "B", 0.9, shared_geography=["Gulf"]), edge("A", "C", 0.9, shared_sectors=["energy"])],
    grounded_only=True,
)
ids = {n["id"] for n in t["nodes"]}
ok("grounded_only: keeps grounded B", "B" in ids)
ok("grounded_only: drops coincidental C", "C" not in ids)

# grounded_only on an all-coincidence root → honest empty
t = trace_consequences("A", EVENTS, [edge("A", "B", 0.9, shared_sectors=["defense"])], grounded_only=True)
ok("grounded_only: all-coincidence root → limited", t["limited"] is True and t["nodes"] == [])

print(f"\ntracer: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
