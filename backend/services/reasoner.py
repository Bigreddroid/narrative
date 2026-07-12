"""
Deep analyst — a DANA-style OODA loop over the event graph, on the local LLM.

The default analyst (``analyst.answer_question``) is a single grounded LLM call.
This is the opt-in "Deep analysis" path: a multi-step Observe → Orient → Decide →
Act loop, modelled on the geolocation OODA precedent (``services/geolocate.py``),
that decomposes the question, investigates each thread against the retrieved
events + CPE exposure, and synthesises a specific answer naming concrete entities,
mechanism, direction, lag, magnitude and a recommended action (R1).

Cost posture is identical to the rest of the platform: it runs **free on local
Ollama**, and every LLM iteration is gated by ``cost_guard`` so a paid hard-cap
trips the chain to a graceful stop — it degrades to a partial/templated answer
rather than erroring or overspending. The loop is bounded to ``MAX_LLM_CALLS``
iterations so a single "deep" request can never fan out unboundedly.
"""

import asyncio
import json
import logging

from backend.services import analyst, cost_guard, llm

logger = logging.getLogger(__name__)

# A single deep request runs at most this many LLM calls end-to-end: 1 Orient +
# up to MAX_THREADS Decide + 1 Act. Keeps a "deep" answer bounded and cheap.
MAX_LLM_CALLS = 6
MAX_THREADS = 3


class _CallBudget:
    """Shared, monotonic call counter so the whole OODA chain honours one cap."""

    def __init__(self, cap: int):
        self.cap = cap
        self.used = 0

    def take(self) -> bool:
        if self.used >= self.cap:
            return False
        self.used += 1
        return True


def _clean_json(text: str) -> str:
    """Strip accidental markdown fences / prose around a JSON value (obj or array)."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        nl = t.find("\n")
        if nl != -1 and t[:nl].strip().lower() in ("json", ""):
            t = t[nl + 1:]
    # Prefer the outermost object; fall back to an array.
    for lo, hi in (("{", "}"), ("[", "]")):
        start, end = t.find(lo), t.rfind(hi)
        if start != -1 and end != -1 and end > start:
            return t[start:end + 1]
    return t


async def _llm(db, system: str, user: str, budget: _CallBudget, max_tokens: int,
               json_mode: bool = False) -> str | None:
    """One cost-gated, budget-counted completion. Returns text, or None when the
    call is not allowed (budget/cap/provider) or the provider errors — callers
    treat None as "stop the chain and synthesise from what we have"."""
    if not budget.take():
        return None
    if not await cost_guard.llm_allowed(db):  # free ollama always passes
        return None
    try:
        result = await asyncio.to_thread(
            llm.complete, system=system, user=user,
            max_tokens=max_tokens, json_mode=json_mode,
        )
        return result.text
    except Exception as exc:  # noqa: BLE001 — never 500 the user; degrade
        logger.warning("reasoner LLM call failed (%s) — degrading", exc)
        return None


_ORIENT_SYSTEM = """You are the lead analyst for The Narrative, a consequence-intelligence
platform. Break the user's question into the few distinct causal THREADS that must each be
investigated to answer it well, USING ONLY the EVENTS and EXPOSURE provided.

Return VALID JSON ONLY (no markdown, no prose outside JSON):
{"threads": [ {"focus": "short label for the angle",
               "why": "1 sentence: which events/sectors make this worth investigating"} ]}
Give 1-3 threads, most decision-relevant first. If the data only supports one angle, return
one. Never invent events or entities that are not in the provided context."""


_DECIDE_SYSTEM = """You are an analyst investigating ONE thread of a larger question, USING
ONLY the EVENTS and EXPOSURE provided. Produce a tight finding for this thread that names:
the specific entities involved, the mechanism (how the effect propagates), the direction
(up/down/disrupt), an approximate lag (how soon), and a rough magnitude. Cite events inline
as [1], [2]. Be concrete; if the data is thin for this thread, say so plainly. 3-5 sentences."""


_ACT_SYSTEM = """You are the analyst for The Narrative. Synthesise the per-thread FINDINGS and
the EXPOSURE summary into one decisive answer for the user, USING ONLY that material.
Requirements:
- Lead with a direct exposure verdict.
- Name specific entities, the mechanism, direction, approximate lag, and rough magnitude.
- End with ONE concrete recommended action for the user's operation.
- Cite events inline as [1], [2] matching the numbers in the context.
- Never invent events, numbers, or outcomes; only say the data can't answer if there is truly
  no relevant event or exposure figure at all."""


def _watched_line(watched: list[str]) -> str:
    return (f"USER'S WATCHED ASSETS (answer about THESE specifically — named suppliers, ports, "
            f"counterparties, companies): {', '.join(watched)}\n\n") if watched else ""


async def _orient(db, question: str, context: str, watched: list[str],
                  budget: _CallBudget) -> list[dict]:
    user = f"{_watched_line(watched)}{context}\n\nQUESTION: {question}"
    raw = await _llm(db, _ORIENT_SYSTEM, user, budget, max_tokens=500, json_mode=True)
    if not raw:
        return []
    try:
        data = json.loads(_clean_json(raw))
    except (json.JSONDecodeError, ValueError):
        return []
    threads = data.get("threads") if isinstance(data, dict) else data
    out: list[dict] = []
    for t in (threads or [])[:MAX_THREADS]:
        if isinstance(t, dict) and (t.get("focus") or "").strip():
            out.append({"focus": str(t["focus"]).strip()[:160],
                        "why": str(t.get("why") or "").strip()[:300]})
    return out


async def _investigate(db, thread: dict, question: str, context: str, watched: list[str],
                       budget: _CallBudget) -> dict | None:
    user = (f"{_watched_line(watched)}{context}\n\nOVERALL QUESTION: {question}\n"
            f"THREAD TO INVESTIGATE: {thread['focus']}"
            + (f" — {thread['why']}" if thread.get("why") else ""))
    raw = await _llm(db, _DECIDE_SYSTEM, user, budget, max_tokens=500)
    if not raw:
        return None
    return {"focus": thread["focus"], "finding": raw.strip()}


async def _act(db, question: str, context: str, findings: list[dict], watched: list[str],
               budget: _CallBudget) -> str | None:
    blocks = "\n".join(f"THREAD — {f['focus']}:\n{f['finding']}" for f in findings)
    user = (f"{_watched_line(watched)}{context}\n\nQUESTION: {question}\n\n"
            f"FINDINGS:\n{blocks}")
    return await _llm(db, _ACT_SYSTEM, user, budget, max_tokens=1024)


async def answer_question_deep(db, question: str, watched_assets: list[str] | None = None) -> dict:
    """Run the deep OODA analyst. Same return shape as ``analyst.answer_question``
    plus a ``trace`` of the reasoning steps and ``deep: True``. Degrades to the
    templated grounded answer if no LLM call can run (provider off / cap hit)."""
    watched = [w.strip() for w in (watched_assets or []) if w and w.strip()][:12]

    # ── OBSERVE ── retrieve grounding, scoped to the user's watched assets.
    events = await analyst.retrieve_events(db, question, watched_assets=watched)
    event_ids = [e["id"] for e in events] or None
    exposure = await analyst.exposure_summary(db, event_ids=event_ids)
    if event_ids and (not exposure or (not exposure.get("sectors") and not exposure.get("pressure"))):
        exposure = await analyst.exposure_summary(db)
    if exposure and exposure.get("regions"):
        keep = set(analyst.clean_regions([r["key"] for r in exposure["regions"]]))
        exposure["regions"] = [r for r in exposure["regions"] if r["key"] in keep]

    top_sectors = [s["key"] for s in (exposure.get("sectors") or [])[:6]] if exposure else []
    top_regions = [r["key"] for r in (exposure.get("regions") or [])][:6] if exposure else []
    pressure = exposure.get("pressure") if exposure else None

    def _result(answer: str, degraded: bool, trace: dict) -> dict:
        return {
            "answer": answer, "sources": events, "pressure": pressure,
            "sectors": top_sectors, "regions": top_regions,
            "degraded": degraded, "deep": True, "trace": trace,
        }

    # No LLM path at all → honest templated answer (never fabricate).
    if not await cost_guard.llm_allowed(db):
        return _result(analyst._templated_answer(events, exposure), True, {"threads": []})

    context = analyst._format_context(events, exposure)
    budget = _CallBudget(MAX_LLM_CALLS)

    # ── ORIENT ── decompose into threads. Fall back to a single implicit thread.
    threads = await _orient(db, question, context, watched, budget)
    if not threads:
        threads = [{"focus": question, "why": ""}]

    # ── DECIDE ── investigate each thread until the call budget/cap is spent.
    findings: list[dict] = []
    for t in threads:
        f = await _investigate(db, t, question, context, watched, budget)
        if f is None:  # budget/cap hit or provider error — stop cleanly
            break
        findings.append(f)

    trace = {"threads": [{"focus": t["focus"], "why": t.get("why", "")} for t in threads],
             "findings": findings}

    # ── ACT ── synthesise. If synthesis can't run, degrade to the best material
    # we produced: the thread findings, else the templated grounded answer.
    final = await _act(db, question, context, findings, watched, budget)
    if final:
        return _result(final.strip(), False, trace)
    if findings:
        stitched = "Live synthesis was cut short (budget reached) — here are the findings so far:\n\n" \
                   + "\n\n".join(f"• {f['focus']}: {f['finding']}" for f in findings)
        return _result(stitched, True, trace)
    return _result(analyst._templated_answer(events, exposure), True, trace)
