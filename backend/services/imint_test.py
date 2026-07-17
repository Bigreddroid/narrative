"""
Property test for IMINT imagery interpretation (Phase 2e). Run from repo root:
    python -m backend.services.imint_test

No real model is called: llm.available / llm.complete_vision are swapped out so the
parsing and self-degrading paths are exercised deterministically and offline.
"""

import sys
from types import SimpleNamespace

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

from backend.services import imint as I
from backend.services import llm

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


_real_available, _real_vision = llm.available, llm.complete_vision


def with_vision(fn):
    """Point the service at a fake vision model for one call."""
    llm.available = lambda: True
    llm.complete_vision = fn


def fake_result(text):
    return SimpleNamespace(text=text, provider="ollama/llava", cost_usd=0.0)


try:
    # ── Self-degrades honestly rather than fabricating an assessment ───────────
    llm.available = lambda: False
    out = I.interpret("Zm9v")
    ok("no model → available False", out["available"] is False)
    ok("honest ceiling is stated even when unavailable",
       "no satellite tasking" in out["scope"].lower())

    def _boom(**_):
        raise RuntimeError("this model is text-only")

    with_vision(_boom)
    out = I.interpret("Zm9v")
    ok("text-only model → available False", out["available"] is False)
    ok("text-only model → reason names the image problem", "image" in out["reason"].lower())

    with_vision(lambda **_: fake_result("I think it's a tank, maybe?"))
    out = I.interpret("Zm9v")
    ok("unparseable model output → available False", out["available"] is False)

    # ── Parses a well-formed assessment into an OODA trace ─────────────────────
    payload = """{
      "observe": ["two revetments with parked rotary aircraft", "fuel bladders nearby"],
      "orient": ["revetments + rotary aircraft => forward helipad"],
      "decide": [
        {"assessment": "Forward arming and refueling point", "confidence": 0.7, "why": "revetments + fuel"},
        {"assessment": "Temporary helipad", "confidence": 0.4, "why": "rotary aircraft"}
      ],
      "act": {"assessment": "Forward arming and refueling point", "facility_type": "FARP",
              "activity": "aircraft parked", "confidence": 0.7, "why": "revetments + fuel"}
    }"""
    with_vision(lambda **_: fake_result(payload))
    out = I.interpret("Zm9v")
    ok("valid payload → available True", out["available"] is True)
    ok("result is tagged IMINT", out["discipline"] == "IMINT")
    ok("headline assessment parsed", out["best"]["assessment"].startswith("Forward arming"))
    ok("act tags carried onto the headline", out["best"]["facility_type"] == "FARP")
    ok("both ranked candidates survive", len(out["trace"]["decide"]) == 2)
    ok("observations survive into the trace", len(out["trace"]["observe"]) == 2)
    ok("confidence is clamped into 0-1", 0.0 <= out["best"]["confidence"] <= 1.0)
    ok("honest ceiling is stated on success too", "no satellite tasking" in out["scope"].lower())

    # ── Tolerates a model that wraps its JSON in markdown fences ───────────────
    fenced = ('```json\n{"observe":["a ship"],"orient":[],'
              '"decide":[{"assessment":"cargo vessel","confidence":0.5,"why":"hull"}],'
              '"act":{"assessment":"cargo vessel","confidence":0.5,"why":"hull"}}\n```')
    with_vision(lambda **_: fake_result(fenced))
    out = I.interpret("Zm9v")
    ok("markdown-fenced JSON is parsed", out["available"] is True
       and out["best"]["assessment"] == "cargo vessel")

    # ── Drops schema echoes instead of reporting them as findings ─────────────
    echo = ('{"observe":["concrete visual facts you actually see","a burning depot"],'
            '"orient":[],"decide":[{"assessment":"struck fuel depot","confidence":0.6,"why":"fire"}],'
            '"act":{"assessment":"struck fuel depot","confidence":0.6,"why":"fire"}}')
    with_vision(lambda **_: fake_result(echo))
    out = I.interpret("Zm9v")
    ok("schema-echo observations are dropped", out["trace"]["observe"] == ["a burning depot"])

    # ── A model that fills the schema with the WRONG SHAPE must degrade, not 502 ──
    # Live llava does this: "decide" comes back as a list of bare strings instead of
    # objects, and _norm_candidate called .get() on a str → AttributeError → the route
    # returned 502. The whole doctrine of this module is to degrade honestly.
    loose = ('{"observe":["a bridge"],"orient":[],'
             '"decide":["a road bridge","a rail bridge"],'
             '"act":{"assessment":"road bridge","confidence":0.6,"why":"deck markings"}}')
    with_vision(lambda **_: fake_result(loose))
    out = I.interpret("Zm9v")
    ok("string candidates don't raise; the act assessment still lands",
       out["available"] is True and out["best"]["assessment"] == "road bridge")

    all_loose = '{"observe":[],"orient":[],"decide":["a road bridge"],"act":"road bridge"}'
    with_vision(lambda **_: fake_result(all_loose))
    out = I.interpret("Zm9v")
    ok("a wholly wrong-shaped payload degrades honestly", out["available"] is False)

    nulls = '{"observe":null,"orient":null,"decide":[null,42],"act":null}'
    with_vision(lambda **_: fake_result(nulls))
    out = I.interpret("Zm9v")
    ok("null/garbage candidates degrade honestly", out["available"] is False)
finally:
    llm.available, llm.complete_vision = _real_available, _real_vision

print(f"\nimint: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
