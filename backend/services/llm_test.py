"""Property tests for the local LLM provider abstraction + cost guard (no DB/network).
Run from repo root:  python -m backend.services.llm_test
"""

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.config import get_settings
from backend.services import cost_guard, llm

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


s = get_settings()  # lru_cached; llm/cost_guard captured this same instance


def _set(provider):
    s.llm_provider = provider


# ── active_provider is local-only (ollama/off); no paid path exists ───────────
_set("ollama")
ok("ollama stays ollama", llm.active_provider() == "ollama")

_set("off")
ok("off stays off", llm.active_provider() == "off")
ok("available() False when provider off", llm.available() is False)

# ── 'off' provider raises BudgetExceeded (callers degrade) ───────────────────
try:
    llm.complete("sys", "user", 10)
    ok("complete raises when off", False)
except llm.BudgetExceeded:
    ok("complete raises when off", True)

# ── cost_guard: the local LLM is free, so a call is always allowed (no DB) ─────
_set("ollama")
ok("claude_allowed always True (local/free, db unused)",
   asyncio.run(cost_guard.claude_allowed(db=None)) is True)

# restore default
_set("ollama")

# ── Vision runs on the VISION model, never the text model ─────────────────────
# Regression guard for a silent failure: _ollama_vision used to send
# settings.local_llm_model, which is text-only by default — so every image request
# degraded to "the active model can't read images" no matter what was pulled. The
# two must stay split (text stays sharp, vision actually sees). No network: we
# intercept the POST and read back the payload.
_sent = {}


class _FakeResp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": "ok"}, "prompt_eval_count": 1, "eval_count": 1}


def _fake_post(url, json=None, timeout=None):
    _sent.update(json or {})
    _sent["__timeout"] = timeout
    return _FakeResp()


_real_post = llm.httpx.post
llm.httpx.post = _fake_post
try:
    s.local_vision_model = "llava:latest"
    s.local_llm_model = "llama3.2:latest"
    llm.complete_vision(system="s", user="u", image_b64="Zm9v")
    ok("vision uses local_vision_model, not local_llm_model", _sent.get("model") == "llava:latest")
    ok("image is attached to the user message", _sent["messages"][1].get("images") == ["Zm9v"])

    # Empty vision model ⇒ fall back to the text model rather than sending model="".
    _sent.clear()
    s.local_vision_model = ""
    llm.complete_vision(system="s", user="u", image_b64="Zm9v")
    ok("empty local_vision_model falls back to local_llm_model",
       _sent.get("model") == "llama3.2:latest")

    # Vision needs its own, longer deadline. Measured live: llava on CPU takes ~90-170s
    # for ONE call, and /imint makes two back-to-back (interpret then geolocate). At the
    # shared 120s text timeout the second call always ReadTimeout'd, so an image could
    # never become an event on the default $0 config — the feature would ship dead.
    _sent.clear()
    s.local_vision_model = "llava:latest"
    llm.complete_vision(system="s", user="u", image_b64="Zm9v")
    ok("vision gets the vision timeout, not the text timeout",
       _sent.get("__timeout") == s.ollama_vision_timeout_seconds)
    ok("the vision deadline is long enough for llava on CPU",
       s.ollama_vision_timeout_seconds >= 300.0)

    _sent.clear()
    llm.complete(system="s", user="u", max_tokens=16)
    ok("text completion keeps the shorter text timeout",
       _sent.get("__timeout") == s.ollama_timeout_seconds)
finally:
    llm.httpx.post = _real_post
    s.local_vision_model = "llava:latest"

# ── normalize_confidence: vision models answer in percent when asked for 0-1 ─────
# Observed live on llava: the geolocate prompt asks for confidence 0-1 and the model
# returns {"confidence": 90.0} meaning 90%. Read naively that is either "out of range,
# discard" (geolocate dropped it to 0.0 — a correct Paris pin arrived as ZERO
# confidence) or "clamp to 1.0" (imint called it 100% certain). Both are wrong, in
# opposite directions, which is exactly why this lives in one place.
ok("0-1 confidence is passed through", llm.normalize_confidence(0.7) == 0.7)
ok("percent confidence is rescaled, not discarded", llm.normalize_confidence(90.0) == 0.9)
ok("percent confidence is rescaled, not clamped to certainty",
   llm.normalize_confidence(90.0) < 1.0)
ok("1.0 stays certain (not read as 1%)", llm.normalize_confidence(1.0) == 1.0)
ok("0 stays zero", llm.normalize_confidence(0) == 0.0)
ok("integer percent works", llm.normalize_confidence(75) == 0.75)
ok("above 100 saturates at certain", llm.normalize_confidence(140) == 1.0)
ok("negative floors at zero", llm.normalize_confidence(-5) == 0.0)
ok("garbage → zero, never raises", llm.normalize_confidence("banana") == 0.0)
ok("None → zero", llm.normalize_confidence(None) == 0.0)

# ── salvage_truncated_json: recover what the model DID finish saying ──────────
# All three fixtures below are REAL llava output, captured live (2026-07-17) by
# running the production imint/geolocate prompts against ollama with a low
# num_predict — the same done_reason=length truncation the 1200-token production
# ceiling produces, just cheaper to reproduce. Do not "fix" their formatting.

# Cut immediately after a dangling key ("act": {"place": "", "country": ← here).
_TRUNC_DANGLING_KEY = '{"observe": ["Concrete road with vehicles on both sides", "Green trees lining one side of the road", "Clear sky overhead", "Overcast clouds in the distance"],\n"orient": ["The road curves gently to the right", "No visible signage indicating language or location"],\n"decide": [{"place": "", "country": "", "lat": 0.0, "lng": 0.0, "confidence": 10, "why": "Insufficient visible geographic clues for accurate geolocation."}],\n"act": {"place": "", "country":'

# Cut mid-KEY inside the first decide candidate ("place ← here, quote never closed).
_TRUNC_MID_KEY = '{\n  "observe": [\n    "The image shows a computer screen with a web page open.",\n    "The title \'world news\' is visible at the top of the screen.",\n    "There are four cards with place names and their corresponding latitude and longitude values, each accompanied by one or two sentences providing a reason for the location",\n    "The text on the image reads \'Welcome to the world, discover what matters most in the world. How does it affect you? Let\'s take a look!\'",\n    "There are icons representing different types of news categories, such as sports, politics, and technology",\n    "The background of the computer screen shows a map with various locations marked."\n  ],\n  "orient": [\n    "The title \'world news\' suggests that the location is likely within an English-speaking country or region, given the term \'world\'"\n  ],\n  "decide": [\n    {\n      "place'

# Cut mid-STRING inside the observe array (the sixth observation never finishes).
_TRUNC_MID_STRING = '{\n  "observe": [\n    "The image displays a computer screen with an interface for a satellite or aerial photo viewing application.",\n    "There is a text box in the upper left corner that reads \'World news\'.",\n    "On the right side, there are several images and icons with various geographical locations marked on them.",\n    "The image shows different colored regions highlighted on the map. These highlights may indicate specific areas of interest or concern.",\n    "There is a menu bar at the top of the screen with options like \'File\', \'Edit\', \'View\', \'Go\', and \'Tools\'.",\n    "Below this, there is another menu bar with sub-options for'

d = llm.salvage_truncated_json(_TRUNC_DANGLING_KEY)
ok("dangling key: the complete decide candidate survives",
   isinstance(d, dict) and d.get("decide", [{}])[0].get("why", "").startswith("Insufficient"))
ok("dangling key: every finished section survives",
   d is not None and len(d.get("observe", [])) == 4 and len(d.get("orient", [])) == 2)
ok("dangling key: the half-emitted pair is dropped, not invented",
   d is not None and "country" not in d.get("act", {"country": "sentinel"}) or d.get("act") == {"place": ""})

d = llm.salvage_truncated_json(_TRUNC_MID_KEY)
ok("mid-key: observe and orient survive in full",
   isinstance(d, dict) and len(d.get("observe", [])) == 6 and len(d.get("orient", [])) == 1)
ok("mid-key: no phantom decide entry is fabricated",
   d is not None and all(x for x in d.get("decide", [])))

d = llm.salvage_truncated_json(_TRUNC_MID_STRING)
ok("mid-string: the five finished observations survive",
   isinstance(d, dict) and len(d.get("observe", [])) == 5)
ok("mid-string: the partial sixth observation is dropped, not half-quoted",
   d is not None and all("sub-options" not in x for x in d.get("observe", [])))

ok("a complete object still parses whole",
   llm.salvage_truncated_json('{"a": [1, 2], "b": {"c": 3}}') == {"a": [1, 2], "b": {"c": 3}})
ok("truncated mid-number: the partial value is dropped",
   llm.salvage_truncated_json('{"lat": 24.7, "confidence": 0.') == {"lat": 24.7})
ok("no JSON at all → None, never raises", llm.salvage_truncated_json("I think it's a tank") is None)
ok("nothing salvageable → None", llm.salvage_truncated_json('{"') is None)
ok("a top-level array is not promoted to a dict", llm.salvage_truncated_json('["a", "b"') is None)

# clean_json — shared fence/prose stripper (imint / geolocate / reasoner)
import json as _json
ok("clean_json strips a ```json fence",
   _json.loads(llm.clean_json('```json\n{"a": 1}\n```')) == {"a": 1})
ok("clean_json strips a bare ``` fence",
   _json.loads(llm.clean_json('```\n{"a": 1}\n```')) == {"a": 1})
ok("clean_json trims surrounding prose",
   _json.loads(llm.clean_json('Sure! Here is the JSON: {"b": 2} — hope that helps')) == {"b": 2})
ok("clean_json falls back to an array when there is no object",
   _json.loads(llm.clean_json('junk [1, 2, 3] more')) == [1, 2, 3])
ok("clean_json prefers the object over a trailing array",
   _json.loads(llm.clean_json('{"x": [1]}')) == {"x": [1]})
ok("clean_json is null-safe", llm.clean_json(None) == "")

print(f"\nllm: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
