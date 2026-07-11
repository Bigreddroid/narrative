"""
Provider-agnostic LLM access.

Free/local by default (Ollama), with Anthropic as an opt-in, hard-capped upgrade.
The whole platform must work with NO paid key: when the active provider is local
or unavailable, callers degrade to free/heuristic paths instead of erroring.

Provider selection (see backend/config.py):
  - llm_provider = "ollama"     → local, free (default)
  - llm_provider = "anthropic"  → paid; honoured ONLY when paid_apis_enabled=True,
                                  and the caller must gate the call with
                                  backend.services.cost_guard.claude_allowed(db).
  - llm_provider = "off"        → no LLM; available()→False.

`complete()` is synchronous so existing callers can keep offloading via
asyncio.to_thread(). Paid budget enforcement lives in cost_guard (async, needs the
DB); this module never spends without the caller first confirming it's allowed.
"""

import logging
from dataclasses import dataclass

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Anthropic pricing for claude-opus-4-8 (consequence_engine_model): $5/MTok in,
# $25/MTok out. Keep in sync with config.consequence_engine_model so the hard cap
# in cost_guard reflects real spend — under-pricing here lets spend overshoot.
_ANTHROPIC_IN_PER_MTOK = 5.0
_ANTHROPIC_OUT_PER_MTOK = 25.0


class BudgetExceeded(RuntimeError):
    """Raised when a paid provider call is blocked (provider 'off' or over cap)."""


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    provider: str


def estimate_anthropic_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * _ANTHROPIC_IN_PER_MTOK + output_tokens * _ANTHROPIC_OUT_PER_MTOK) / 1_000_000


def active_provider() -> str:
    """The provider actually used right now. Reads the runtime override (set via the
    admin Settings panel) falling back to the env default. Paid 'anthropic' still
    downgrades to local when the master switch is off, so neither a stray config NOR a
    runtime flip can start spending unless the deploy explicitly enabled paid APIs."""
    from backend.services import runtime_config  # lazy: avoids a model import at load

    p = runtime_config.llm_provider()
    if p == "anthropic" and not settings.paid_apis_enabled:
        return "ollama"
    return p


def is_paid() -> bool:
    return active_provider() == "anthropic"


def available() -> bool:
    """Can the active provider serve a request right now? Cheap, side-effect-free."""
    p = active_provider()
    if p == "off":
        return False
    if p == "anthropic":
        return bool(settings.anthropic_api_key)
    if p == "ollama":
        return _ollama_up()
    return False


def complete(system: str, user: str, max_tokens: int, json_mode: bool = False) -> LLMResult:
    """Single completion. Raises BudgetExceeded if provider is 'off', or the
    provider's own error (e.g. httpx/anthropic) on failure — callers degrade."""
    p = active_provider()
    if p == "off":
        raise BudgetExceeded("LLM provider is 'off'")
    if p == "ollama":
        return _ollama_complete(system, user, max_tokens, json_mode)
    if p == "anthropic":
        return _anthropic_complete(system, user, max_tokens)
    raise BudgetExceeded(f"unknown llm_provider: {p}")


def complete_vision(
    system: str,
    user: str,
    image_b64: str,
    media_type: str = "image/jpeg",
    max_tokens: int = 1024,
    json_mode: bool = False,
) -> LLMResult:
    """Multimodal completion over a single base64-encoded image.

    Every Claude model is vision-capable, so the anthropic path always works. The
    ollama path only works if local_llm_model is a multimodal model (e.g. llava,
    llama3.2-vision) — a text-only local model returns a provider error and the
    caller degrades. Same budget posture as complete(): never spends unless the
    active provider is paid AND the caller already confirmed it's allowed."""
    p = active_provider()
    if p == "off":
        raise BudgetExceeded("LLM provider is 'off'")
    if p == "ollama":
        return _ollama_vision(system, user, image_b64, max_tokens, json_mode)
    if p == "anthropic":
        return _anthropic_vision(system, user, image_b64, media_type, max_tokens)
    raise BudgetExceeded(f"unknown llm_provider: {p}")


# ── Ollama (local, free) ──────────────────────────────────────────────────────
def _ollama_up() -> bool:
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _ollama_complete(system: str, user: str, max_tokens: int, json_mode: bool) -> LLMResult:
    payload: dict = {
        "model": settings.local_llm_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"num_predict": max_tokens},
    }
    if json_mode:
        payload["format"] = "json"

    r = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json=payload,
        timeout=settings.ollama_timeout_seconds,
    )
    r.raise_for_status()
    data = r.json()
    text = (data.get("message") or {}).get("content", "").strip()
    if not text:
        raise ValueError("Ollama returned an empty completion")
    return LLMResult(
        text=text,
        input_tokens=data.get("prompt_eval_count", 0),
        output_tokens=data.get("eval_count", 0),
        cost_usd=0.0,
        provider="ollama",
    )


def _ollama_vision(system: str, user: str, image_b64: str, max_tokens: int, json_mode: bool) -> LLMResult:
    # Ollama's chat API takes images as a base64 list on the user message. Only
    # multimodal models (llava, llama3.2-vision, …) accept them; a text model
    # errors, which the caller catches and degrades on.
    payload: dict = {
        "model": settings.local_llm_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user, "images": [image_b64]},
        ],
        "options": {"num_predict": max_tokens},
    }
    if json_mode:
        payload["format"] = "json"

    r = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json=payload,
        timeout=settings.ollama_timeout_seconds,
    )
    r.raise_for_status()
    data = r.json()
    text = (data.get("message") or {}).get("content", "").strip()
    if not text:
        raise ValueError("Ollama returned an empty vision completion")
    return LLMResult(
        text=text,
        input_tokens=data.get("prompt_eval_count", 0),
        output_tokens=data.get("eval_count", 0),
        cost_usd=0.0,
        provider="ollama",
    )


# ── Anthropic (paid, opt-in, hard-capped by the caller) ───────────────────────
def _anthropic_complete(system: str, user: str, max_tokens: int) -> LLMResult:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    resp = client.messages.create(
        model=settings.consequence_engine_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = resp.content[0].text.strip()
    in_tok = resp.usage.input_tokens
    out_tok = resp.usage.output_tokens
    return LLMResult(
        text=text,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=estimate_anthropic_cost(in_tok, out_tok),
        provider="anthropic",
    )


def _anthropic_vision(system: str, user: str, image_b64: str, media_type: str, max_tokens: int) -> LLMResult:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    resp = client.messages.create(
        model=settings.consequence_engine_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": user},
            ],
        }],
    )
    text = resp.content[0].text.strip()
    in_tok = resp.usage.input_tokens
    out_tok = resp.usage.output_tokens
    return LLMResult(
        text=text,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=estimate_anthropic_cost(in_tok, out_tok),
        provider="anthropic",
    )
