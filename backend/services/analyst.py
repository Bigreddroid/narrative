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
        else:
            # No semantic hits (embedder off, or no events carry embeddings). This is
            # the usual cause of "same answer every question" in prod — log it so the
            # fallback is visible instead of silent.
            logger.info("analyst retrieval: semantic ranking unavailable for %r — "
                        "using keyword/importance fallback", query[:60])
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


# Sub-national / NWS-zone water & county words that pollute the exposure "regions"
# list. Keep countries, chokepoints and blocs; drop US zone names ("albemarle sound",
# "croatan and roanoke sounds", "lake pontchartrain", "los angeles county") so the
# readout reads like a geopolitics desk, not a weather bulletin. Matched as whole
# tokens ANYWHERE in the name (not just the tail) so plurals and "lake X" prefixes go.
_REGION_NOISE_WORDS = {
    "sound", "sounds", "river", "rivers", "inlet", "inlets", "creek", "creeks",
    "bay", "bayou", "lake", "lakes", "county", "parish", "channel", "harbor",
    "harbour", "reservoir", "slough", "marsh", "lagoon",
}


def clean_regions(regions: list[str]) -> list[str]:
    """Drop sub-national US zone/county noise from an exposure region list.

    Removes: names containing a noise word (any token), "City, Country" pairs (comma),
    and names whose last token is a 2-letter state/zone code ("allen ks").
    """
    out = []
    for r in regions or []:
        s = (r or "").strip()
        if not s or "," in s:
            continue
        toks = re.findall(r"[a-z]+", s.lower())
        if any(t in _REGION_NOISE_WORDS for t in toks):
            continue
        if toks and len(toks[-1]) == 2:  # trailing state/zone code
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
async def exposure_summary(db, event_ids: list | None = None) -> dict | None:
    """Compact CPE summary {pressure, sectors, regions} reusing the exposure route's helpers.

    When ``event_ids`` is given (the events retrieved for a specific question), the
    exposure is computed over just those events so the readout is question-specific,
    not the same global top-importance list under every answer. Falls back to the
    global graph when no ids are supplied."""
    try:
        from backend.api.routes.exposure import _load_graph, _combined_stress, PAID_TIER_EVENT_LIMIT
        from backend.consequence_engine import corroboration, propagation
        events, edges = await _load_graph(db, PAID_TIER_EVENT_LIMIT, event_ids=event_ids)
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
    # Question-scoped exposure: compute the CPE over the events retrieved for THIS
    # question, so the pressure/sectors/regions readout differs per question instead
    # of showing the same global top list under every answer.
    event_ids = [e["id"] for e in events] or None
    exposure = await exposure_summary(db, event_ids=event_ids)
    # The question's events may not carry consequence maps yet (e.g. OSINT/news events
    # that haven't been mapped) — then the scoped model is blank (pressure 0, no sectors).
    # Fall back to the global exposure so the readout stays meaningful rather than empty,
    # while still preferring the question-scoped model whenever it has real signal.
    if event_ids and (not exposure or (not exposure.get("sectors") and not exposure.get("pressure"))):
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
