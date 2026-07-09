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
- Lead with a direct exposure verdict. The EXPOSURE line (overall pressure, top sectors,
  top regions) is real computed data — treat it as first-class evidence and translate it
  into concrete consequences: name which sectors and regions are exposed and why, even
  when the individual EVENTS touch the topic only indirectly.
- Cite the events you use inline as [1], [2], etc. matching the numbers given.
- Be concise and concrete: lead with the answer, then the consequence reasoning.
- Only say the data can't answer when there are NO events AND no exposure figures at all.
  Never invent events, numbers, or outcomes, and never use outside knowledge as our data.
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


# Generic question words that carry no retrieval signal — dropped before keyword match
# so "what is my exposure to X" ranks on X, not on "exposure"/"impact".
_STOPWORDS = {
    "the", "and", "for", "with", "about", "does", "will", "would", "that", "this",
    "what", "which", "when", "where", "whom", "your", "yours", "mine", "have", "from",
    "into", "over", "under", "exposure", "exposed", "impact", "impacts", "affect",
    "affects", "affected", "risk", "risks", "happening", "going", "should", "could",
}


def _salient_terms(query: str) -> list[str]:
    """Meaningful ≥4-letter words from the question, de-duped, order preserved."""
    seen: set[str] = set()
    out: list[str] = []
    for t in re.findall(r"[a-z]{4,}", (query or "").lower()):
        if t not in _STOPWORDS and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:8]


async def _keyword_events(db, query: str, limit: int):
    """Literal term matches over mapped events, split by strength.

    Returns (strong, weak): ``strong`` events match ≥2 distinct salient terms in the
    title/summary — a reliable sign this is the very event the question names — and
    are surfaced even when they carry NO embedding (≈⅔ of the graph), which the
    semantic-only path silently drops."""
    terms = _salient_terms(query)
    if not terms:
        return [], []
    conds = []
    for t in terms:
        pat = f"%{t}%"
        conds.append(NarrativeEvent.canonical_title.ilike(pat))
        conds.append(NarrativeEvent.canonical_summary.ilike(pat))
    rows = (await db.execute(
        select(NarrativeEvent).where(NarrativeEvent.is_mapped == True)  # noqa: E712
        .where(or_(*conds))
        .order_by(NarrativeEvent.global_importance_score.desc()).limit(limit * 2)
    )).scalars().all()

    def _hits(e) -> int:
        blob = f"{e.canonical_title or ''} {e.canonical_summary or ''}".lower()
        return sum(1 for t in terms if t in blob)

    strong = [e for e in rows if _hits(e) >= 2]
    weak = [e for e in rows if _hits(e) < 2]
    return strong, weak


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
    """Question-specific mapped events, blending literal + semantic signals.

    Order: strong keyword matches (≥2 salient terms — the event the question actually
    names) → semantic (pgvector) neighbours → weak keyword matches → top-importance
    headlines. Blending the keyword pass is what lets an on-topic event that carries no
    embedding still surface; semantic-only silently drops ~⅔ of the graph and is the
    usual cause of the analyst "missing" the very event asked about."""
    events: list = []
    seen: set = set()

    def _extend(rows) -> None:
        for e in rows:
            if e.id not in seen:
                seen.add(e.id)
                events.append(e)

    if query:
        strong_kw, weak_kw = await _keyword_events(db, query, limit)
        _extend(strong_kw)  # multi-term literal hits lead — includes unembedded events

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
            _extend(sorted(rows, key=lambda e: rank.get(e.id, 10_000)))
        elif not strong_kw:
            # No semantic ranking AND no strong literal hit — log so the degraded
            # (importance-only) retrieval is visible rather than silent.
            logger.info("analyst retrieval: semantic ranking unavailable for %r — "
                        "using keyword/importance fallback", query[:60])

        _extend(weak_kw)  # single-term literal hits fill remaining slots

    if not events:  # no query, or nothing matched → top headline events
        events = (await db.execute(
            select(NarrativeEvent).where(NarrativeEvent.is_mapped == True)  # noqa: E712
            .order_by(NarrativeEvent.global_importance_score.desc()).limit(limit)
        )).scalars().all()
    return [_event_dict(e) for e in events[:limit]]


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
    # Over-fetch, then drop US NWS-zone/county noise ("Pamlico Sound", "S of Currituck
    # Beach Light NC…") through the canonical filter before capping, so the risk-hotspots
    # readout shows real countries/regions rather than sub-national marine-zone strings.
    ranked = aggregate_country_risk(
        [{"geography": g, "importance": imp, "last_updated_at": ts} for g, imp, ts in rows],
        top=top * 4)
    keep = set(clean_regions([r["country"] for r in ranked]))
    return [r for r in ranked if r["country"] in keep][:top]


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
    # Strip US zone/county noise from the exposure regions ONCE, at the source, so every
    # downstream consumer — the LLM context, the templated fallback, and the returned
    # readout — sees clean regions instead of "albemarle sound, allen ks" leaking through.
    if exposure and exposure.get("regions"):
        _keep = set(clean_regions([r["key"] for r in exposure["regions"]]))
        exposure["regions"] = [r for r in exposure["regions"] if r["key"] in _keep]
    # Consequence readout the UI shows under the answer (trade/shipping/logistics
    # exposure), personalised client-side against the user's sectors/region.
    top_sectors = [s["key"] for s in (exposure.get("sectors") or [])[:6]] if exposure else []
    top_regions = [r["key"] for r in (exposure.get("regions") or [])][:6] if exposure else []

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
