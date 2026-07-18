"""
Agentic operator — the AI operator loop where Narrative's OWN LLM calls the
platform's read-only intelligence tools mid-reasoning (Palantir-AIP-style, but
$0-local).

Unlike ``services/reasoner.py`` (which loops by re-prompting with fixed system
prompts and parsing JSON), this loop hands the model TOOLS (see
``services/operator_tools.py``) and lets IT decide which to call — search the
graph, pull exposure, trace a consequence chain, surface cross-discipline
convergence — before writing a grounded answer. Every tool is read-only; any
"action" would return a proposal for human approval, never a side effect.

Cost/safety posture matches the rest of the platform: free on local Ollama,
every LLM turn gated by ``cost_guard`` and bounded by ``MAX_LLM_CALLS`` so a
single request can never fan out unboundedly. If the local model can't drive
tools (or anything fails), the loop degrades to the deep reasoner — which itself
degrades to a templated grounded answer — so the feature never hard-fails.
"""

import asyncio
import json
import logging

from backend.services import analyst, cost_guard, llm, reasoner
from backend.services.operator_tools import TOOL_SCHEMAS, run_tool

logger = logging.getLogger(__name__)

# One agentic request runs at most this many LLM turns (each turn may issue tool
# calls). Parity with reasoner.MAX_LLM_CALLS. Keeps latency + cost bounded.
MAX_LLM_CALLS = 6
MAX_CALLS_PER_TURN = 4          # tools executed per assistant turn
_TOOL_RESULT_CHARS = 3500       # cap each tool result fed back into context

OPERATOR_SYSTEM = """You are the AI operator for The Narrative, a consequence-intelligence
platform. Answer the user's question by CALLING TOOLS to gather live evidence, then writing a
decisive, grounded answer.

Method:
- Start by calling tools — do not answer from memory. Typical flow: search_events to find the
  relevant events, get_exposure for the sector/region risk picture, cross_discipline to see what
  is genuinely connected across intelligence domains, and trace_consequences on a key event id to
  follow the cascade.
- Call tools one or a few at a time; use earlier results to decide the next call. Stop calling
  tools once you have enough to answer.
- Before asserting a key claim, consider grade_sources to check HOW TRUSTWORTHY the evidence is
  (its NATO Admiralty reliability grade, e.g. "B2") — and say so when the grade is weak.
- Then write the final answer: lead with a direct exposure verdict; name specific entities, the
  mechanism, direction (up/down/disrupt), approximate lag and rough magnitude; end with ONE
  concrete recommended action. Ground every claim in tool results — never invent events or numbers.
- If the tools return little, say so plainly rather than speculating."""


def _summarize(name: str, result: dict) -> str:
    """One-line human summary of a tool result for the reasoning trace."""
    if not isinstance(result, dict):
        return str(result)[:160]
    if "error" in result:
        return f"error: {result['error']}"
    if name == "search_events":
        return f"{result.get('count', 0)} events"
    if name == "get_exposure":
        secs = ", ".join(s.get("key", "") for s in (result.get("sectors") or [])[:3])
        return f"pressure {result.get('pressure')}; sectors {secs or 'n/a'}"
    if name == "country_risk":
        cs = result.get("countries") or []
        return f"{len(cs)} countries; top {cs[0]['country'] if cs else 'n/a'}"
    if name == "trace_consequences":
        return f"{len(result.get('nodes') or [])} nodes, {len(result.get('hops') or [])} hops"
    if name == "cross_discipline":
        return f"{result.get('count', 0)} cross-discipline convergences"
    if name == "grade_sources":
        g = (result.get("graded") or [])
        top = g[0]["grade"] if g else "n/a"
        return f"{len(g)} graded; top {top}"
    return "ok"


def _harvest(name: str, result: dict, sources: dict, exposure_holder: dict) -> None:
    """Pull citable events + any exposure readout out of a tool result so the final
    payload can populate the UI (sources list + pressure/sectors/regions)."""
    if not isinstance(result, dict) or "error" in result:
        return
    for e in result.get("events") or []:
        if e.get("id"):
            sources.setdefault(e["id"], e)
    if name == "get_exposure" and (result.get("pressure") is not None or result.get("sectors")):
        exposure_holder["exposure"] = result


async def answer_question_agentic(db, question: str, watched_assets: list[str] | None = None) -> dict:
    """Run the agentic operator loop. Returns the analyst payload shape
    (answer, sources, pressure, sectors, regions, degraded) plus ``mode:"agent"``
    and ``trace`` (the ordered tool calls). Falls back to the deep reasoner on any
    failure or if the local model does not drive tools."""
    watched = [w.strip() for w in (watched_assets or []) if w and w.strip()][:12]

    # No LLM budget at all → straight to the reasoner (which degrades to templated).
    if not await cost_guard.llm_allowed(db):
        return await _fallback(db, question, watched, trace=[], reason="no-llm")

    watched_line = (f"USER'S WATCHED ASSETS (answer about THESE specifically): "
                    f"{', '.join(watched)}\n" if watched else "")
    messages: list[dict] = [
        {"role": "system", "content": OPERATOR_SYSTEM},
        {"role": "user", "content": f"{watched_line}QUESTION: {question}"},
    ]

    trace: list[dict] = []
    sources: dict[str, dict] = {}
    exposure_holder: dict = {}
    tools_ran = 0

    try:
        for _ in range(MAX_LLM_CALLS):
            if not await cost_guard.llm_allowed(db):
                break
            res = await asyncio.to_thread(llm.complete_tools, messages, TOOL_SCHEMAS, 1024)

            if not res.tool_calls:
                # Model answered. If it never used a tool, it's ungrounded → fall back.
                if tools_ran == 0:
                    return await _fallback(db, question, watched, trace, reason="no-tools")
                if res.text:
                    return await _finalize(db, res.text.strip(), sources, exposure_holder, trace)
                break

            # Append the assistant turn, then run each requested tool and feed results back.
            messages.append(res.raw_message or {"role": "assistant", "content": res.text})
            for call in res.tool_calls[:MAX_CALLS_PER_TURN]:
                result = await run_tool(db, call.name, call.arguments)
                tools_ran += 1
                trace.append({"tool": call.name, "args": call.arguments,
                              "summary": _summarize(call.name, result)})
                _harvest(call.name, result, sources, exposure_holder)
                messages.append({
                    "role": "tool", "tool_name": call.name,
                    "content": json.dumps(result, default=str)[:_TOOL_RESULT_CHARS],
                })
    except Exception as exc:  # noqa: BLE001 — any transport/model failure degrades cleanly
        logger.warning("operator loop failed (%s) — falling back to deep reasoner", exc)
        return await _fallback(db, question, watched, trace, reason="error")

    # Budget spent without a final free-text answer → ask once more for synthesis, else fall back.
    if tools_ran:
        messages.append({"role": "user", "content":
                         "Write the final grounded answer now from the tool results above."})
        try:
            res = await asyncio.to_thread(llm.complete_tools, messages, [], 1024)
            if res.text:
                return await _finalize(db, res.text.strip(), sources, exposure_holder, trace)
        except Exception as exc:  # noqa: BLE001
            logger.warning("operator synthesis failed (%s)", exc)
    return await _fallback(db, question, watched, trace, reason="budget")


async def _finalize(db, answer: str, sources: dict, exposure_holder: dict, trace: list[dict]) -> dict:
    """Assemble the analyst-shaped payload from harvested tool evidence."""
    exposure = exposure_holder.get("exposure")
    if not exposure:  # model never called get_exposure — populate the readout anyway
        event_ids = list(sources.keys()) or None
        exposure = await analyst.exposure_summary(db, event_ids=event_ids) \
            or {"pressure": None, "sectors": [], "regions": []}
    return {
        "answer": answer,
        "sources": list(sources.values()),
        "pressure": exposure.get("pressure"),
        "sectors": [s["key"] for s in (exposure.get("sectors") or [])[:6]],
        "regions": [r["key"] for r in (exposure.get("regions") or [])[:6]],
        "degraded": False,
        "mode": "agent",
        "trace": trace,
    }


async def _fallback(db, question: str, watched: list[str], trace: list[dict], reason: str) -> dict:
    """Degrade to the deep reasoner (itself degrades to a templated grounded answer),
    tagging the payload so the UI/tests can see the operator handed off and why."""
    logger.info("operator → deep reasoner fallback (reason=%s)", reason)
    deep = await reasoner.answer_question_deep(db, question, watched_assets=watched)
    deep["mode"] = "agent-fallback"
    deep["fallback_reason"] = reason
    if trace:
        deep["tool_trace"] = trace
    return deep
