"""
Analyst service — shared retrieval + grounding brain behind the AI chat
(POST /api/v1/chat) and the MCP server.

Grounds answers ONLY in real platform data: the live event graph + the CPE
exposure model. Never fabricates — if the retrieved context can't answer, the
model is told to say so. Pure helpers (_format_context, aggregate_country_risk)
are unit-tested without an LLM call.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import or_, select

from backend.config import get_settings
from backend.models.narrative_event import NarrativeEvent

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_CONTEXT_EVENTS = 12

ANALYST_SYSTEM = """You are the analyst for The Narrative, a world consequence-intelligence platform.
Answer the user's question USING ONLY the numbered EVENTS and the EXPOSURE summary provided.
Rules:
- Cite the events you use inline as [1], [2], etc. matching the numbers given.
- Be concise and concrete: lead with the answer, then the consequence reasoning.
- If the provided context cannot answer the question, say so plainly — do NOT invent
  events, numbers, or outcomes. Never use outside knowledge as if it were our data.
"""


# ── retrieval ────────────────────────────────────────────────────────────────
async def retrieve_events(db, query: str | None, limit: int = MAX_CONTEXT_EVENTS) -> list[dict]:
    """Relevant mapped events: text-matched when a query is given, else top importance."""
    stmt = select(NarrativeEvent).where(NarrativeEvent.is_mapped == True)  # noqa: E712
    if query:
        pat = f"%{query}%"
        stmt = stmt.where(or_(
            NarrativeEvent.canonical_title.ilike(pat),
            NarrativeEvent.canonical_summary.ilike(pat),
            NarrativeEvent.category.ilike(pat),
        ))
    stmt = stmt.order_by(NarrativeEvent.global_importance_score.desc()).limit(limit)
    events = (await db.execute(stmt)).scalars().all()
    # Fallback: if a text query matched nothing, ground on the top headline events
    # so the model still has real context instead of guessing.
    if query and not events:
        events = (await db.execute(
            select(NarrativeEvent).where(NarrativeEvent.is_mapped == True)  # noqa: E712
            .order_by(NarrativeEvent.global_importance_score.desc()).limit(limit)
        )).scalars().all()
    return [{
        "id": str(e.id),
        "title": e.canonical_title,
        "summary": e.canonical_summary,
        "category": e.category,
        "status": e.current_status,
        "importance": e.global_importance_score,
        "geography": e.geographic_relevance or [],
    } for e in events]


# ── pure helpers (unit-tested, no DB/LLM) ────────────────────────────────────
def _format_context(events: list[dict], exposure: dict | None) -> str:
    lines = []
    if exposure:
        top_sec = ", ".join(f"{s['key']} {s['score']}" for s in (exposure.get("sectors") or [])[:5])
        top_reg = ", ".join(f"{r['key']} {r['score']}" for r in (exposure.get("regions") or [])[:5])
        lines.append(f"EXPOSURE — overall pressure {exposure.get('pressure')}. "
                     f"Top sectors: {top_sec or 'n/a'}. Top regions: {top_reg or 'n/a'}.")
    lines.append("EVENTS:")
    for i, e in enumerate(events, 1):
        geo = ", ".join(e.get("geography") or [])
        lines.append(f"[{i}] ({e['category']}/{e['status']}, importance {e['importance']}) "
                     f"{e['title']} — {(e.get('summary') or '')[:200]} [{geo}]")
    return "\n".join(lines)


def aggregate_country_risk(rows: list[dict], now: datetime | None = None, top: int = 20) -> list[dict]:
    """Per-country risk = sum(importance × time-decay) over events touching that country.

    rows: [{geography: [str], importance: int, last_updated_at: datetime|None}]
    Decay: half-life ~7 days. Pure + deterministic for testing.
    """
    now = now or datetime.now(timezone.utc)
    scores: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        imp = r.get("importance") or 0
        ts = r.get("last_updated_at")
        if ts is not None:
            age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
            decay = 0.5 ** (age_days / 7.0)
        else:
            decay = 0.5
        for country in (r.get("geography") or []):
            if not country:
                continue
            scores[country] += imp * decay
            counts[country] += 1
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top]
    return [{"country": c, "risk": round(s, 1), "events": counts[c]} for c, s in ranked]


# ── orchestration ────────────────────────────────────────────────────────────
async def exposure_summary(db) -> dict | None:
    """Compact CPE summary {pressure, sectors, regions} reusing the exposure route's helpers."""
    try:
        from backend.api.routes.exposure import _load_graph, _combined_stress, PAID_TIER_EVENT_LIMIT
        from backend.consequence_engine import corroboration, propagation
        events, edges = await _load_graph(db, PAID_TIER_EVENT_LIMIT)
        if not events:
            return None
        model = propagation.compute_exposure_model(
            events, edges, market_stress=await _combined_stress(db),
            corroboration=corroboration.corroborate(events))
        return {"pressure": model.get("pressure"),
                "sectors": model.get("sectors", []), "regions": model.get("regions", [])}
    except Exception as exc:  # noqa: BLE001 — chat still works without the exposure block
        logger.warning("exposure_summary failed: %s", exc)
        return None


async def country_risk(db, top: int = 20) -> list[dict]:
    rows = (await db.execute(
        select(NarrativeEvent.geographic_relevance, NarrativeEvent.global_importance_score,
               NarrativeEvent.last_updated_at)
        .where(NarrativeEvent.is_mapped == True)  # noqa: E712
        .order_by(NarrativeEvent.global_importance_score.desc()).limit(500)
    )).all()
    return aggregate_country_risk(
        [{"geography": g, "importance": imp, "last_updated_at": ts} for g, imp, ts in rows], top=top)


async def answer_question(db, question: str) -> dict:
    """Retrieve real context, ask Claude grounded in it, return {answer, sources, pressure}."""
    import anthropic
    events = await retrieve_events(db, question)
    exposure = await exposure_summary(db)
    context = _format_context(events, exposure)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    resp = client.messages.create(
        model=settings.consequence_engine_model,
        max_tokens=1024,
        system=ANALYST_SYSTEM,
        messages=[{"role": "user", "content": f"{context}\n\nQUESTION: {question}"}],
    )
    answer = resp.content[0].text.strip()
    return {
        "answer": answer,
        "sources": events,  # [n] citations in the answer map to this 1-indexed list
        "pressure": exposure.get("pressure") if exposure else None,
    }
