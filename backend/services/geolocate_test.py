"""
Property tests for vision geolocation parsing — specifically the truncation-salvage
path added with the IMINT-robustness work. Run from repo root:
    python -m backend.services.geolocate_test

No real model is called: llm.available / llm.complete_vision are swapped out so the
parsing and self-degrading paths are exercised deterministically and offline. The
truncated payloads are REAL llava output, captured live (2026-07-17) by running the
production geolocate prompt against ollama with a low num_predict — the same
done_reason=length truncation the 1200-token production ceiling produces.
"""

import sys
from types import SimpleNamespace

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

from backend.services import geolocate as G
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
    # ── Baseline honesty: no model, no location ────────────────────────────────
    llm.available = lambda: False
    out = G.geolocate("Zm9v")
    ok("no model → available False", out["available"] is False)

    with_vision(lambda **_: fake_result("somewhere in Europe, probably"))
    out = G.geolocate("Zm9v")
    ok("unparseable output → available False", out["available"] is False)

    # ── Truncation cut off "act" after a dangling key — the decide candidate is
    # complete, so the pin the model DID finish earning must survive. Before the
    # salvage path this whole read-out was discarded as unparseable. ────────────
    dangling_act = '{"observe": ["Concrete road with vehicles on both sides", "Green trees lining one side of the road", "Clear sky overhead", "Overcast clouds in the distance"],\n"orient": ["The road curves gently to the right", "No visible signage indicating language or location"],\n"decide": [{"place": "", "country": "", "lat": 0.0, "lng": 0.0, "confidence": 10, "why": "Insufficient visible geographic clues for accurate geolocation."}],\n"act": {"place": "", "country":'
    with_vision(lambda **_: fake_result(dangling_act))
    out = G.geolocate("Zm9v")
    ok("truncated act: the completed decide candidate becomes the pin",
       out["available"] is True and out["best"]["why"].startswith("Insufficient"))
    ok("truncated act: observations survive into the trace",
       len(out["trace"]["observe"]) == 4)
    ok("truncated act: llava's percent confidence is normalized, not trusted",
       out["best"]["confidence"] == 0.10)

    # ── Truncation cut mid-key before ANY candidate finished — there is nothing
    # honest to pin, and the distinct "no plausible location" reason (instead of
    # "did not return a usable location") proves the salvaged parse degraded, not
    # the JSON parser. ─────────────────────────────────────────────────────────
    mid_key = '{\n  "observe": [\n    "The image shows a computer screen with a web page open.",\n    "The title \'world news\' is visible at the top of the screen.",\n    "There are four cards with place names and their corresponding latitude and longitude values, each accompanied by one or two sentences providing a reason for the location",\n    "The text on the image reads \'Welcome to the world, discover what matters most in the world. How does it affect you? Let\'s take a look!\'",\n    "There are icons representing different types of news categories, such as sports, politics, and technology",\n    "The background of the computer screen shows a map with various locations marked."\n  ],\n  "orient": [\n    "The title \'world news\' suggests that the location is likely within an English-speaking country or region, given the term \'world\'"\n  ],\n  "decide": [\n    {\n      "place'
    with_vision(lambda **_: fake_result(mid_key))
    out = G.geolocate("Zm9v")
    ok("truncated before any candidate: no pin is fabricated",
       out["available"] is False and "plausible location" in out["reason"])
finally:
    llm.available, llm.complete_vision = _real_available, _real_vision

print(f"\ngeolocate: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
