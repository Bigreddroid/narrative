"""
Unit tests for the agentic operator loop (services/operator.py) — no DB, no LLM.

We stub llm.complete_tools (the transport), run_tool (the tool bodies) and the
cost gate, so the tests exercise ONLY the loop's control flow: tool dispatch,
evidence harvesting, termination on budget, and the fallbacks. Run:

    PYTHONPATH="$PWD" python backend/services/operator_test.py
"""

import asyncio

from backend.services import operator_loop as operator
from backend.services import operator_tools as OT
from backend.services.llm import LLMResult, ToolCall

passed = failed = 0


def ok(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {label}")
    else:
        failed += 1
        print(f"FAIL  {label}")


def _res(text="", calls=None):
    return LLMResult(text=text, input_tokens=0, output_tokens=0, cost_usd=0.0,
                     provider="stub", tool_calls=calls or [],
                     raw_message={"role": "assistant", "content": text, "tool_calls": calls or []})


class _Patch:
    """Monkeypatch operator's collaborators for one scenario, restoring on exit."""
    def __init__(self, complete_tools=None, run_tool=None, deep=None, allowed=True):
        self._saved = {}
        self.complete_tools = complete_tools
        self.run_tool = run_tool
        self.deep = deep
        self.allowed = allowed

    def __enter__(self):
        async def _allowed(_db):
            return self.allowed
        self._saved["ct"] = operator.llm.complete_tools
        self._saved["rt"] = operator.run_tool
        self._saved["deep"] = operator.reasoner.answer_question_deep
        self._saved["cg"] = operator.cost_guard.llm_allowed
        if self.complete_tools:
            operator.llm.complete_tools = self.complete_tools
        if self.run_tool:
            operator.run_tool = self.run_tool
        if self.deep:
            operator.reasoner.answer_question_deep = self.deep
        operator.cost_guard.llm_allowed = _allowed
        return self

    def __exit__(self, *a):
        operator.llm.complete_tools = self._saved["ct"]
        operator.run_tool = self._saved["rt"]
        operator.reasoner.answer_question_deep = self._saved["deep"]
        operator.cost_guard.llm_allowed = self._saved["cg"]


# canned tool outputs
_TOOL_OUT = {
    "search_events": {"events": [{"id": "e1", "title": "Strait closure"}], "count": 1},
    "get_exposure": {"pressure": 42, "sectors": [{"key": "Energy", "score": 90}], "regions": []},
    "cross_discipline": {"cross_discipline": [{"event_id": "e1", "disciplines": ["CYBINT", "FININT"]}], "count": 1},
}


async def _run_tool_stub(db, name, args):
    return _TOOL_OUT.get(name, {"ok": True})


# ── 1. registry schemas well-formed ──────────────────────────────────────────
ok("every tool schema is a function with a registered name",
   all(s.get("type") == "function" and s["function"]["name"] in OT.TOOL_NAMES for s in OT.TOOL_SCHEMAS))
ok("six tools registered", len(OT.TOOL_SCHEMAS) == 6 and "grade_sources" in OT.TOOL_NAMES)
ok("unknown tool returns an error (never raises)",
   asyncio.run(OT.run_tool(None, "does_not_exist", {})).get("error", "").startswith("unknown tool"))


# ── 2. happy path: tools drive the answer, evidence harvested ────────────────
def _script_then_answer():
    seq = iter([
        _res(calls=[ToolCall("search_events", {"query": "gulf"}), ToolCall("get_exposure", {})]),
        _res(calls=[ToolCall("cross_discipline", {})]),
        _res(text="Energy is most exposed via the strait. Action: pre-position stock."),
    ])
    def stub(messages, tools, max_tokens=1024, model=None):
        return next(seq)
    return stub


with _Patch(complete_tools=_script_then_answer(), run_tool=_run_tool_stub):
    out = asyncio.run(operator.answer_question_agentic(None, "gulf exposure?"))
ok("mode is agent", out.get("mode") == "agent")
ok("final answer returned", out["answer"].startswith("Energy is most exposed"))
ok("trace records all 3 tool calls", [t["tool"] for t in out["trace"]] ==
   ["search_events", "get_exposure", "cross_discipline"])
ok("exposure harvested into readout", out["pressure"] == 42 and out["sectors"] == ["Energy"])
ok("sources harvested from search_events", any(s["id"] == "e1" for s in out["sources"]))
ok("not degraded", out["degraded"] is False)


# ── 3. termination: model never stops calling tools → bounded, then synthesises ──
def _never_final():
    def stub(messages, tools, max_tokens=1024, model=None):
        if tools == []:                       # synthesis request (tools stripped)
            return _res(text="Synthesised from the evidence gathered.")
        return _res(calls=[ToolCall("search_events", {"query": "x"})])
    return stub


with _Patch(complete_tools=_never_final(), run_tool=_run_tool_stub):
    out = asyncio.run(operator.answer_question_agentic(None, "loop?"))
ok("loop bounded to MAX_LLM_CALLS turns", len(out["trace"]) == operator.MAX_LLM_CALLS)
ok("falls through to synthesis answer", out["answer"].startswith("Synthesised"))


# ── 4. fallback: model answers WITHOUT calling any tool → deep reasoner ───────
async def _deep_stub(db, question, watched_assets=None):
    return {"answer": "deep grounded answer", "sources": [], "deep": True}


with _Patch(complete_tools=lambda *a, **k: _res(text="ungrounded guess"),
            run_tool=_run_tool_stub, deep=_deep_stub):
    out = asyncio.run(operator.answer_question_agentic(None, "q?"))
ok("no-tools answer falls back to reasoner", out.get("mode") == "agent-fallback")
ok("fallback reason recorded", out.get("fallback_reason") == "no-tools")
ok("fallback carries the reasoner's answer", out["answer"] == "deep grounded answer")


# ── 5. fallback: transport raises → degrade cleanly ──────────────────────────
def _boom(*a, **k):
    raise RuntimeError("ollama down")


with _Patch(complete_tools=_boom, run_tool=_run_tool_stub, deep=_deep_stub):
    out = asyncio.run(operator.answer_question_agentic(None, "q?"))
ok("transport error degrades to fallback", out.get("mode") == "agent-fallback")
ok("error fallback reason recorded", out.get("fallback_reason") == "error")


# ── 6. no LLM budget → straight to fallback, no tools ────────────────────────
with _Patch(complete_tools=_boom, run_tool=_run_tool_stub, deep=_deep_stub, allowed=False):
    out = asyncio.run(operator.answer_question_agentic(None, "q?"))
ok("no-budget skips the loop entirely", out.get("fallback_reason") == "no-llm")


# ── 7. grade_sources tool body: real corroboration + Admiralty grading, no DB ──
# Stub the graph loader and the triage-history query (the only DB touches) so the
# grader itself runs for real: three independent feeds converging in geo+time.
import backend.api.routes.exposure as _EXPO
import backend.services.source_reliability as _SR

_saved_lg, _saved_sh = _EXPO._load_graph, _SR.source_history_map
_TS = 1_700_000_000_000.0


async def _fake_load_graph(db, limit, event_ids=None):
    return [
        {"id": "e1", "canonical_title": "Strait incident", "source": "reuters",
         "discipline": "HUMINT", "lat": 26.5, "lng": 56.3, "ts": _TS},
        {"id": "e2", "canonical_title": "Strait incident (sensor)", "source": "usgs",
         "discipline": "MASINT", "lat": 26.5, "lng": 56.3, "ts": _TS + 1000},
        {"id": "e3", "canonical_title": "Strait incident (wire)", "source": "bbc",
         "discipline": "CYBINT", "lat": 26.5, "lng": 56.3, "ts": _TS + 2000},
    ], []


async def _fake_history(db, sources):
    return {}  # no track record → grade from provenance + corroboration only


_EXPO._load_graph = _fake_load_graph
_SR.source_history_map = _fake_history
try:
    out = asyncio.run(OT._grade_sources(None))                 # global (no scope)
    one = asyncio.run(OT._grade_sources(None, event_id="e2"))  # single-event filter
finally:
    _EXPO._load_graph, _SR.source_history_map = _saved_lg, _saved_sh

ok("grade_sources grades every event in scope", out["count"] == 3 and len(out["graded"]) == 3)
ok("each entry carries a 2-char Admiralty grade",
   all(isinstance(g["grade"], str) and len(g["grade"]) == 2 for g in out["graded"]))
ok("3 independent feeds -> credibility digit <= 2 (probably true / confirmed)",
   all(int(g["grade"][1]) <= 2 for g in out["graded"]))
ok("strongest source (usgs -> A) sorts first", out["graded"][0]["grade"][0] == "A")
ok("rationale is auditable (non-empty list)",
   all(isinstance(g["rationale"], list) and g["rationale"] for g in out["graded"]))
ok("event_id scopes output to that one event", one["count"] == 1 and one["graded"][0]["event_id"] == "e2")


print(f"\noperator: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
