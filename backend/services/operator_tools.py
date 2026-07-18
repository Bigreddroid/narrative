"""
Operator tool registry — the read-only intelligence tools Narrative's own LLM may
call mid-reasoning (see backend/services/operator.py).

Each tool wraps an EXISTING service/engine function in-process over the request's
``db`` — nothing new is computed here, and every tool is strictly read-only. A core
subset of these capabilities is also exposed to external MCP clients by
backend/mcp_server.py (over HTTP); this module is the richer in-process registry the
agent loop calls without a network hop. Tool bodies never raise: on any failure they return
``{"error": ...}`` so one bad tool can't crash the loop.
"""

import logging

from backend.services import analyst

logger = logging.getLogger(__name__)

# Bounds so a single tool call can't pull the whole graph into the context window.
_MAX_EVENTS = 10
_MAX_TRACE_FANOUT = 60
_MAX_CROSS_DISC = 12


# ── tool bodies (all read-only, all degrade to {"error": ...}) ────────────────
async def _search_events(db, query: str = "", limit: int = 8, **_) -> dict:
    """Question-specific events blending keyword + semantic retrieval."""
    events = await analyst.retrieve_events(db, query or "", limit=min(int(limit or 8), _MAX_EVENTS))
    return {"events": events, "count": len(events)}


async def _get_exposure(db, query: str | None = None, **_) -> dict:
    """CPE exposure {pressure, sectors, regions}. Scoped to a query's events when given,
    else the global graph."""
    event_ids = None
    if query:
        events = await analyst.retrieve_events(db, query, limit=_MAX_EVENTS)
        event_ids = [e["id"] for e in events] or None
    summary = await analyst.exposure_summary(db, event_ids=event_ids)
    if not summary or (not summary.get("sectors") and not summary.get("pressure")):
        summary = await analyst.exposure_summary(db)  # fall back to global signal
    if summary and summary.get("regions"):
        keep = set(analyst.clean_regions([r["key"] for r in summary["regions"]]))
        summary["regions"] = [r for r in summary["regions"] if r["key"] in keep]
    return summary or {"pressure": None, "sectors": [], "regions": []}


async def _country_risk(db, top: int = 15, **_) -> dict:
    """Ranked per-country risk hotspots (importance × recency)."""
    return {"countries": await analyst.country_risk(db, top=min(int(top or 15), 30))}


async def _trace_consequences(db, event_id: str = "", depth: int = 3, **_) -> dict:
    """Directed multi-hop consequence chain FROM an event id (as returned by search_events)."""
    import uuid

    from sqlalchemy import or_, select

    from backend.api.routes.exposure import _load_graph
    from backend.consequence_engine.tracer import trace_consequences
    from backend.models.event_connection import EventConnection
    from backend.models.narrative_event import NarrativeEvent

    try:
        eid = uuid.UUID(str(event_id))
    except (ValueError, AttributeError):
        return {"error": f"invalid event_id: {event_id!r} — use an id from search_events"}
    if not await db.get(NarrativeEvent, eid):
        return {"error": "event not found"}
    neigh = (await db.execute(
        select(EventConnection.event_a_id, EventConnection.event_b_id)
        .where(or_(EventConnection.event_a_id == eid, EventConnection.event_b_id == eid))
        .order_by(EventConnection.connection_weight.desc()).limit(_MAX_TRACE_FANOUT)
    )).all()
    ids = {eid}
    for a, b in neigh:
        ids.add(a)
        ids.add(b)
    events, edges = await _load_graph(db, len(ids), event_ids=[str(i) for i in ids])
    depth = max(1, min(int(depth or 3), 4))
    return trace_consequences(str(eid), events, edges, depth=depth, max_nodes=25)


async def _cross_discipline(db, query: str | None = None, **_) -> dict:
    """Events where independent feeds from DIFFERENT INT disciplines (HUMINT/CYBINT/
    FININT/MASINT/…) converge on the same place+time — the multi-INT fusion signal,
    i.e. what is genuinely 'connected' across domains rather than one feed echoing."""
    from backend.api.routes.exposure import PAID_TIER_EVENT_LIMIT, _load_graph
    from backend.consequence_engine import corroboration

    event_ids = None
    if query:
        events = await analyst.retrieve_events(db, query, limit=_MAX_EVENTS)
        event_ids = [e["id"] for e in events] or None
    events, _edges = await _load_graph(db, PAID_TIER_EVENT_LIMIT, event_ids=event_ids)
    title = {e["id"]: e.get("canonical_title") for e in events}
    corr = corroboration.corroborate(events)
    multi = [
        {"event_id": eid, "title": title.get(eid), "index": v["index"],
         "count": v["count"], "disciplines": v["disciplines"], "sources": v["sources"]}
        for eid, v in corr.items()
        if len(v.get("disciplines") or []) > 1 and v["count"] > 0
    ]
    multi.sort(key=lambda x: x["index"], reverse=True)
    return {"cross_discipline": multi[:_MAX_CROSS_DISC], "count": len(multi)}


async def _grade_sources(db, query: str | None = None, event_id: str | None = None,
                         top: int = 8, **_) -> dict:
    """NATO Admiralty reliability grade for the events in scope — the same deterministic,
    no-LLM grader the /wipro fusion strip shows. Each event gets a letter (source
    reliability, from provenance + OSINT-triage track record) and a digit (information
    credibility, from how many INDEPENDENT feeds corroborate it in geo+time), e.g. "B2",
    with an auditable rationale. The grade *rises with corroboration*.

    Scope: a `query` grades convergence WITHIN that topic's events (view-scoped, same as
    the /events/corroboration endpoint); an `event_id` grades that one event against the
    broader graph. With neither, the strongest-graded events overall are returned."""
    from backend.api.routes.exposure import PAID_TIER_EVENT_LIMIT, _load_graph
    from backend.consequence_engine import corroboration
    from backend.services import source_reliability

    wanted: set | None = None
    if event_id:
        # One event vs. the whole graph: load the global slice, filter the OUTPUT.
        events, _edges = await _load_graph(db, PAID_TIER_EVENT_LIMIT)
        wanted = {str(event_id)}
    elif query:
        # View-scoped: corroborate only within the topic's events (endpoint parity).
        hits = await analyst.retrieve_events(db, query, limit=_MAX_EVENTS)
        ids = [e["id"] for e in hits] or None
        events, _edges = await _load_graph(db, _MAX_EVENTS, event_ids=ids)
    else:
        events, _edges = await _load_graph(db, PAID_TIER_EVENT_LIMIT)

    corr = corroboration.corroborate(events)
    await source_reliability.attach_grades(db, corr, events)  # adds entry["reliability"]

    meta = {e["id"]: e for e in events}
    graded = [
        {
            "event_id": eid,
            "title": meta.get(eid, {}).get("canonical_title"),
            "source": meta.get(eid, {}).get("source"),
            "grade": v["reliability"]["grade"],
            "reliability": v["reliability"]["reliability"]["label"],
            "credibility": v["reliability"]["credibility"]["label"],
            "corroborating_sources": v.get("count", 0),
            "disciplines": v.get("disciplines") or [],
            "rationale": v["reliability"]["rationale"],
        }
        for eid, v in corr.items()
        if "reliability" in v and (wanted is None or eid in wanted)
    ]
    # Strongest first: grade string sorts "A1" < "B2" < "F6"; break ties on corroboration.
    graded.sort(key=lambda g: (g["grade"], -g["corroborating_sources"]))
    graded = graded[: max(1, min(int(top or 8), _MAX_EVENTS))]
    return {"graded": graded, "count": len(graded)}


_MAX_PROPOSALS = 6


async def _propose_watchlist_add(db, entities=None, reason: str = "", **_) -> dict:
    """Propose entities for the user's watchlist. NEVER writes — the operator is
    read-only; this only surfaces a suggestion the UI turns into a one-click, human-
    approved 'Add to watchlist'. Each proposed name is grounded against the live graph
    (does the platform actually see events about it?) so the user is never asked to
    watch something with no signal behind it."""
    if isinstance(entities, str):
        entities = entities.split(",")
    seen: set = set()
    norm: list[str] = []
    for e in (entities or []):
        name = str(e).strip()[:80]
        key = name.lower()
        if name and key not in seen:
            seen.add(key)
            norm.append(name)
        if len(norm) >= _MAX_PROPOSALS:
            break
    if not norm:
        return {"error": "no entities proposed"}

    grounded: list[str] = []
    for name in norm:
        try:
            hits = await analyst.retrieve_events(db, name, limit=1)
        except Exception:  # noqa: BLE001 — grounding is best-effort; absence ≠ failure
            hits = []
        if hits:
            grounded.append(name)

    return {
        "proposal": {"entities": norm, "reason": str(reason or "").strip()[:300]},
        "grounded": grounded,
        "ungrounded": [n for n in norm if n not in grounded],
        "requires_approval": True,
        "note": "Proposed watchlist additions — the user must approve before anything is saved.",
    }


# ── registry: name → (callable, JSON schema) ─────────────────────────────────
_REGISTRY: dict[str, dict] = {
    "search_events": {
        "fn": _search_events,
        "schema": {
            "type": "function",
            "function": {
                "name": "search_events",
                "description": "Search the live event graph for events relevant to a query "
                               "(title/summary/geography). Returns events with ids you can pass "
                               "to trace_consequences.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "what to search for"},
                        "limit": {"type": "integer", "description": "max events (default 8)"},
                    },
                    "required": ["query"],
                },
            },
        },
    },
    "get_exposure": {
        "fn": _get_exposure,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_exposure",
                "description": "Consequence-exposure model: overall pressure + per-sector and "
                               "per-region risk scores. Optionally scope to a query's events.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "optional topic to scope exposure to"},
                    },
                },
            },
        },
    },
    "country_risk": {
        "fn": _country_risk,
        "schema": {
            "type": "function",
            "function": {
                "name": "country_risk",
                "description": "Ranked per-country risk hotspots (importance × recency) over the graph.",
                "parameters": {
                    "type": "object",
                    "properties": {"top": {"type": "integer", "description": "how many (default 15)"}},
                },
            },
        },
    },
    "trace_consequences": {
        "fn": _trace_consequences,
        "schema": {
            "type": "function",
            "function": {
                "name": "trace_consequences",
                "description": "Directed multi-hop consequence chain FROM an event: how its effects "
                               "cascade to other events. Pass an event_id from search_events.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string", "description": "event id from search_events"},
                        "depth": {"type": "integer", "description": "hops to walk, 1-4 (default 3)"},
                    },
                    "required": ["event_id"],
                },
            },
        },
    },
    "cross_discipline": {
        "fn": _cross_discipline,
        "schema": {
            "type": "function",
            "function": {
                "name": "cross_discipline",
                "description": "Events where feeds from DIFFERENT intelligence disciplines "
                               "(HUMINT/CYBINT/FININT/MASINT/…) converge on the same place+time — "
                               "the multi-INT fusion signal for what is truly connected across domains.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "optional topic to scope to"},
                    },
                },
            },
        },
    },
    "grade_sources": {
        "fn": _grade_sources,
        "schema": {
            "type": "function",
            "function": {
                "name": "grade_sources",
                "description": "NATO Admiralty source-reliability grade (e.g. 'B2') for events: a "
                               "letter for how reliable the source is and a digit for how well the "
                               "report is corroborated — with an auditable rationale. Use it to weigh "
                               "HOW TRUSTWORTHY your evidence is before asserting it. Pass a query to "
                               "grade a topic, or an event_id from search_events to grade one event.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "topic to grade"},
                        "event_id": {"type": "string",
                                     "description": "grade a single event id from search_events"},
                    },
                },
            },
        },
    },
    "propose_watchlist_add": {
        "fn": _propose_watchlist_add,
        "schema": {
            "type": "function",
            "function": {
                "name": "propose_watchlist_add",
                "description": "Propose one or more entities (a company, supplier, port, country, "
                               "counterparty) for the user's watchlist when the analysis shows they "
                               "keep driving consequences the user cares about. This does NOT save "
                               "anything — it surfaces a suggestion the user approves with one click. "
                               "Use sparingly, only for entities central to your answer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entities": {"type": "array", "items": {"type": "string"},
                                     "description": "entity names to propose (max 6)"},
                        "reason": {"type": "string",
                                   "description": "one sentence: why these are worth watching"},
                    },
                    "required": ["entities"],
                },
            },
        },
    },
}

TOOL_SCHEMAS: list[dict] = [t["schema"] for t in _REGISTRY.values()]
TOOL_NAMES: list[str] = list(_REGISTRY.keys())


async def run_tool(db, name: str, arguments: dict) -> dict:
    """Execute a registered read-only tool. Never raises — returns {"error": ...} on
    an unknown tool or any internal failure, so the agent loop stays alive."""
    entry = _REGISTRY.get(name)
    if not entry:
        return {"error": f"unknown tool: {name}", "available": TOOL_NAMES}
    try:
        return await entry["fn"](db, **(arguments or {}))
    except TypeError as exc:  # bad/extra args from the model
        return {"error": f"bad arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001 — a tool failure must not kill the loop
        logger.warning("operator tool %s failed: %s", name, exc)
        return {"error": f"{name} failed: {exc}"}
