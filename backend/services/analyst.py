"""
Analyst service — shared retrieval + grounding brain behind the AI chat
(POST /api/v1/chat) and the MCP server.

Grounds answers ONLY in real platform data: the live event graph + the CPE
exposure model. Never fabricates — if the retrieved context can't answer, the
model is told to say so. Pure helpers (_format_context, aggregate_country_risk)
are unit-tested without an LLM call.
"""

import asyncio
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import or_, select, text

from backend.config import get_settings
from backend.models.narrative_event import NarrativeEvent
from backend.services import cost_guard, llm

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
async def _semantic_event_ids(db, query: str, limit: int) -> list:
    """Top mapped-event ids by embedding similarity to the question (pgvector).

    This is what makes retrieval question-specific: "how does the war affect India"
    lands on the Iran/India/Gulf events instead of the generic top-importance ones.
    Returns [] (→ caller falls back) if embeddings are unavailable."""
    from backend.consequence_engine.embedder import embed_texts
    vec = (await asyncio.to_thread(embed_texts, [query]))[0]
    if not vec or not any(vec):  # zero vector ⇒ embedder failed; don't rank on noise
        return []
    emb = "[" + ",".join(str(float(v)) for v in vec) + "]"
    rows = (await db.execute(
        text("SELECT id FROM narrative_events "
             "WHERE is_mapped = true AND embedding IS NOT NULL "
             "ORDER BY embedding <=> CAST(:emb AS vector(1024)) LIMIT :lim"),
        {"emb": emb, "lim": limit},
    )).all()
    return [r[0] for r in rows]


def _event_dict(e) -> dict:
    return {
        "id": str(e.id),
        "title": e.canonical_title,
        "summary": e.canonical_summary,
        "category": e.category,
        "status": e.current_status,
        "importance": e.global_importance_score,
        "geography": e.geographic_relevance or [],
    }


async def retrieve_events(db, query: str | None, limit: int = MAX_CONTEXT_EVENTS) -> list[dict]:
    """Question-specific mapped events: semantic (pgvector) → keyword → top importance."""
    events = []
    if query:
        try:
            ids = await _semantic_event_ids(db, query, limit)
        except Exception as exc:  # noqa: BLE001 — never fail the answer on retrieval
            logger.warning("semantic retrieval failed (%s) — falling back", exc)
            ids = []
        if ids:
            rows = (await db.execute(
                select(NarrativeEvent).where(NarrativeEvent.id.in_(ids))
            )).scalars().all()
            rank = {i: n for n, i in enumerate(ids)}
            events = sorted(rows, key=lambda e: rank.get(e.id, 10_000))
        if not events:  # keyword fallback
            pat = f"%{query}%"
            events = (await db.execute(
                select(NarrativeEvent).where(NarrativeEvent.is_mapped == True)  # noqa: E712
                .where(or_(
                    NarrativeEvent.canonical_title.ilike(pat),
                    NarrativeEvent.canonical_summary.ilike(pat),
                    NarrativeEvent.category.ilike(pat),
                ))
                .order_by(NarrativeEvent.global_importance_score.desc()).limit(limit)
            )).scalars().all()
    if not events:  # no query, or nothing matched → top headline events
        events = (await db.execute(
            select(NarrativeEvent).where(NarrativeEvent.is_mapped == True)  # noqa: E712
            .order_by(NarrativeEvent.global_importance_score.desc()).limit(limit)
        )).scalars().all()
    return [_event_dict(e) for e in events]


# Sub-national / NWS-zone noise that pollutes the exposure "regions" list. Keep
# countries, chokepoints and blocs; drop US county/zone names ("allen ks",
# "albemarle sound") so the readout reads like a geopolitics desk, not a weather bulletin.
_REGION_NOISE = re.compile(
    r"\b(?:sound|rivers?|inlet|creek|bay|lake|county|channel|harbou?r|reservoir|[a-z]{2})$",
    re.I)


def clean_regions(regions: list[str]) -> list[str]:
    """Drop sub-national US zone/county noise from an exposure region list."""
    out = []
    for r in regions or []:
        s = (r or "").strip()
        if not s or "," in s or _REGION_NOISE.search(s.lower()):
            continue
        out.append(s)
    return out


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


def _templated_answer(events: list[dict], exposure: dict | None) -> str:
    """Grounded answer assembled WITHOUT an LLM — used when live synthesis is off
    (no LLM available or the paid cap is hit). Honest, never fabricated."""
    if not events:
        return ("Live AI synthesis is currently off and there are no mapped events to "
                "summarise yet. Try again once the pipeline has mapped some events.")
    parts = ["Live AI synthesis is off — here is the most relevant real data on file:"]
    if exposure and exposure.get("pressure") is not None:
        top_sec = ", ".join(s["key"] for s in (exposure.get("sectors") or [])[:3])
        top_reg = ", ".join(r["key"] for r in (exposure.get("regions") or [])[:3])
        parts.append(
            f"Overall pressure is {exposure['pressure']}"
            + (f"; top sectors: {top_sec}" if top_sec else "")
            + (f"; top regions: {top_reg}" if top_reg else "") + "."
        )
    parts.append("Top events:")
    for i, e in enumerate(events[:5], 1):
        geo = ", ".join(e.get("geography") or [])
        parts.append(
            f"[{i}] {e['title']} — {e.get('category')}/{e.get('status')}, "
            f"importance {e.get('importance')}" + (f" ({geo})" if geo else "")
        )
    return "\n".join(parts)


async def answer_question(db, question: str) -> dict:
    """Retrieve real context, answer grounded in it, return {answer, sources, pressure}.

    Free/local LLM by default. When no LLM is available (or a paid provider has hit
    its hard cap), degrade to a templated, grounded answer instead of erroring."""
    events = await retrieve_events(db, question)
    exposure = await exposure_summary(db)
    # Consequence readout the UI shows under the answer (trade/shipping/logistics
    # exposure), personalised client-side against the user's sectors/region.
    top_sectors = [s["key"] for s in (exposure.get("sectors") or [])[:6]] if exposure else []
    top_regions = clean_regions([r["key"] for r in (exposure.get("regions") or [])])[:6] if exposure else []

    if not await cost_guard.llm_allowed(db):
        return {
            "answer": _templated_answer(events, exposure),
            "sources": events,
            "pressure": exposure.get("pressure") if exposure else None,
            "sectors": top_sectors,
            "regions": top_regions,
            "degraded": True,
        }

    context = _format_context(events, exposure)
    try:
        result = await asyncio.to_thread(
            llm.complete,
            system=ANALYST_SYSTEM,
            user=f"{context}\n\nQUESTION: {question}",
            max_tokens=1024,
        )
        answer, degraded = result.text, False
    except Exception as exc:  # noqa: BLE001 — never 500 the user; fall back to context
        logger.warning("Analyst LLM call failed (%s) — returning templated answer", exc)
        answer, degraded = _templated_answer(events, exposure), True

    return {
        "answer": answer,
        "sources": events,  # [n] citations in the answer map to this 1-indexed list
        "pressure": exposure.get("pressure") if exposure else None,
        "sectors": top_sectors,
        "regions": top_regions,
        "degraded": degraded,
    }
