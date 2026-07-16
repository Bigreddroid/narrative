"""
Provider-agnostic LLM access — local-only.

The whole platform runs on a free, local LLM (Ollama). There is no paid LLM
provider: when the active provider is unavailable, callers degrade to
free/heuristic paths instead of erroring, so nothing here ever needs an API key.

Provider selection (see backend/config.py):
  - llm_provider = "ollama"  → local, free (default)
  - llm_provider = "off"     → no LLM; available()→False.

`complete()` is synchronous so existing callers can keep offloading via
asyncio.to_thread().
"""

import json
import logging
from dataclasses import dataclass, field

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Local models occasionally return an empty completion (transient); re-request before failing.
_OLLAMA_EMPTY_RETRIES = 3


class BudgetExceeded(RuntimeError):
    """Raised when no LLM call can proceed (provider 'off')."""


@dataclass
class ToolCall:
    """One tool the model asked to run. ``arguments`` is already-parsed JSON (dict)."""

    name: str
    arguments: dict


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    provider: str
    # Populated only by complete_tools(): the tools the model chose to call, plus the
    # raw assistant message to append back to the conversation for the next turn.
    tool_calls: list = field(default_factory=list)
    raw_message: dict | None = None


def active_provider() -> str:
    """The provider actually used right now. Reads the runtime override (set via the
    admin Settings panel) falling back to the env default. Only local providers exist,
    so this is always 'ollama' or 'off' — no path can start paid spend."""
    from backend.services import runtime_config  # lazy: avoids a model import at load

    return runtime_config.llm_provider()


def available() -> bool:
    """Can the active provider serve a request right now? Cheap, side-effect-free."""
    p = active_provider()
    if p == "off":
        return False
    if p == "ollama":
        return _ollama_up()
    return False


def complete(
    system: str, user: str, max_tokens: int, json_mode: bool = False, model: str | None = None
) -> LLMResult:
    """Single completion. Raises BudgetExceeded if provider is 'off', or the
    provider's own error (e.g. httpx) on failure — callers degrade.

    `model` overrides the local Ollama model for this call only (e.g. a worker that
    needs a more reliable model than the global default)."""
    p = active_provider()
    if p == "off":
        raise BudgetExceeded("LLM provider is 'off'")
    if p == "ollama":
        return _ollama_complete(system, user, max_tokens, json_mode, model)
    raise BudgetExceeded(f"unknown llm_provider: {p}")


def complete_tools(
    messages: list[dict], tools: list[dict], max_tokens: int = 1024, model: str | None = None
) -> LLMResult:
    """Agentic completion: give the model TOOLS it may call. Returns an LLMResult whose
    ``tool_calls`` lists the tools the model wants run (empty when it answered directly)
    and ``raw_message`` is the assistant turn to append back before feeding tool results.

    ``messages`` is a full chat history (system + user + prior assistant/tool turns).
    Raises BudgetExceeded if provider is 'off'; the caller degrades to a non-agentic path."""
    p = active_provider()
    if p == "off":
        raise BudgetExceeded("LLM provider is 'off'")
    if p == "ollama":
        return _ollama_tools(messages, tools, max_tokens, model)
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

    The ollama path only works if local_llm_model is a multimodal model (e.g. llava,
    llama3.2-vision) — a text-only local model returns a provider error and the caller
    degrades. `media_type` is accepted for API symmetry but not needed by Ollama."""
    p = active_provider()
    if p == "off":
        raise BudgetExceeded("LLM provider is 'off'")
    if p == "ollama":
        return _ollama_vision(system, user, image_b64, max_tokens, json_mode)
    raise BudgetExceeded(f"unknown llm_provider: {p}")


# ── Ollama (local, free) ──────────────────────────────────────────────────────
def _ollama_up() -> bool:
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _ollama_complete(
    system: str, user: str, max_tokens: int, json_mode: bool, model: str | None = None
) -> LLMResult:
    payload: dict = {
        "model": model or settings.local_llm_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"num_predict": max_tokens},
    }
    if json_mode:
        payload["format"] = "json"

    # Some local models (notably gemma on a strict json-format constraint) intermittently
    # return an empty completion with done_reason=stop. It's transient — a re-request on
    # the same prompt usually succeeds — so retry a few times before giving up.
    text = ""
    data: dict = {}
    for _ in range(_OLLAMA_EMPTY_RETRIES):
        r = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
            timeout=settings.ollama_timeout_seconds,
        )
        r.raise_for_status()
        data = r.json()
        text = (data.get("message") or {}).get("content", "").strip()
        if text:
            break
    if not text:
        raise ValueError(
            f"Ollama returned an empty completion after {_OLLAMA_EMPTY_RETRIES} attempts "
            f"(model={payload['model']!r})"
        )
    return LLMResult(
        text=text,
        input_tokens=data.get("prompt_eval_count", 0),
        output_tokens=data.get("eval_count", 0),
        cost_usd=0.0,
        provider="ollama",
    )


def _ollama_tools(
    messages: list[dict], tools: list[dict], max_tokens: int, model: str | None = None
) -> LLMResult:
    # Ollama's /api/chat accepts OpenAI-style `tools` and returns `message.tool_calls`
    # (arguments already parsed to a dict, unlike OpenAI which returns a JSON string).
    # Tool-capable local models: llama3.2, qwen2.5, mistral-nemo, … A model without
    # tool support simply returns content and no tool_calls — the caller falls back.
    payload: dict = {
        "model": model or settings.local_llm_model,
        "stream": False,
        "messages": messages,
        "tools": tools,
        "options": {"num_predict": max_tokens},
    }
    r = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json=payload,
        timeout=settings.ollama_timeout_seconds,
    )
    r.raise_for_status()
    data = r.json()
    msg = data.get("message") or {}
    calls: list[ToolCall] = []
    for c in msg.get("tool_calls") or []:
        fn = c.get("function") or {}
        name = fn.get("name")
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, ValueError):
                args = {}
        if name:
            calls.append(ToolCall(name=str(name), arguments=args if isinstance(args, dict) else {}))
    return LLMResult(
        text=(msg.get("content") or "").strip(),
        input_tokens=data.get("prompt_eval_count", 0),
        output_tokens=data.get("eval_count", 0),
        cost_usd=0.0,
        provider="ollama",
        tool_calls=calls,
        raw_message=msg,
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
