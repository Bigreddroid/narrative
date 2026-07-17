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

print(f"\nllm: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
