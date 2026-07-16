"""
Operator tool registry — the read-only intelligence tools Narrative's own LLM may
call mid-reasoning (see backend/services/operator.py).

Each tool wraps an EXISTING service/engine function in-process over the request's
``db`` — nothing new is computed here, and every tool is strictly read-only. The
same five capabilities are exposed to external MCP clients by backend/mcp_server.py
(over HTTP); this module is the in-process mirror so the agent loop can call them
without a network hop. Tool bodies never raise: on any failure they return
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
