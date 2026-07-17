"""
IMINT — imagery-intelligence interpretation of PROVIDED imagery, as an OODA trace.

Phase 2e closes the platform's biggest discipline gap. Given an image an operator
already has (a photo, a screenshot, an open-source frame), a vision-LLM reads out
what is militarily / intelligence-relevant in it — installations, platforms,
vehicles, infrastructure, activity — and SHOWS ITS WORK in the Observe → Orient →
Decide → Act loop so a human can judge every call. This is the honest counter to a
black-box "AI says tank": each finding is tied to a concrete visual cue.

Scope is deliberately, honestly bounded at $0: this is INTERPRETATION of imagery the
user supplies. There is **no satellite tasking and no commercial-imagery purchase** —
we never pretend to own a constellation. It runs free on a local multimodal Ollama
model (llava, already pulled), or on Claude vision when paid APIs are enabled; if no
vision model can serve the request it degrades to an honest "unavailable" result
rather than fabricating an assessment. Modeled on services/geolocate.py.
"""

import json
import logging

from backend.services import llm

logger = logging.getLogger(__name__)

# Honest ceiling label, surfaced with every result so the capability is never oversold.
SCOPE_NOTE = ("Interpretation of provided imagery only — no satellite tasking, no "
              "commercial-imagery purchase.")

_SYSTEM = """You are an imagery-intelligence (IMINT) analyst. You interpret a SINGLE
provided image and you SHOW YOUR WORK so a human can check every call. You do not
guess beyond what is visible, and you never claim access to satellites or other imagery.

Work through the OODA loop, filling each field with your OWN findings about THIS image:
- observe: the concrete visual facts you actually see — structures, vehicles, aircraft,
  vessels, weapons/equipment, terrain, infrastructure, markings/insignia, visible
  activity, time-of-day/weather cues. State only what is visible.
- orient: intelligence inferences, each tied to one observation above (e.g. "revetments
  + parked rotary aircraft ⇒ forward operating helipad").
- decide: 2-4 ranked candidate assessments of what this imagery shows (most likely
  first), each with a one-sentence reason citing the evidence and a confidence 0-1.
- act: your single best assessment, copied from the top "decide" entry, plus a short
  "facility_type" tag and any "activity" noted.

Return VALID JSON ONLY (no markdown, no prose outside JSON) in exactly this shape, with
the empty strings and zeros replaced by your actual findings:
{
  "observe": [],
  "orient": [],
  "decide": [{"assessment": "", "confidence": 0.0, "why": ""}],
  "act": {"assessment": "", "facility_type": "", "activity": "", "confidence": 0.0, "why": ""}
}
Rules: report only what is visible. Be honest — if evidence is thin, say so in "why" and
lower the confidence. Never invent markings or equipment you cannot actually see, and
never echo these field descriptions back as if they were observations."""

_USER = ("Interpret this image as imagery intelligence. Extract every usable visual cue, "
         "reason step by step, and return the JSON schema exactly.")


def _clean_json(text: str) -> str:
    """Strip accidental markdown fences and any prose around the JSON object."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        nl = t.find("\n")
        if nl != -1 and t[:nl].strip().lower() in ("json", ""):
            t = t[nl + 1:]
    start, end = t.find("{"), t.rfind("}")
    return t[start:end + 1] if start != -1 and end != -1 else t


def _conf(v):
    # Shared with geolocate: a bare clamp here read llava's percent answer (90.0) as
    # absolute certainty (1.0). See llm.normalize_confidence.
    return llm.normalize_confidence(v)


# Substrings that signal a model echoed the schema's guidance instead of real findings.
_PLACEHOLDER_MARKERS = (
    "concrete visual facts",
    "intelligence inferences",
    "each tied to",
    "structures, vehicles, aircraft",
)


def _is_placeholder(s: str) -> bool:
    t = s.strip().lower()
    if not t or set(t) <= {".", "…", "-", "_"}:
        return True
    return any(m in t for m in _PLACEHOLDER_MARKERS)


def _strings(v) -> list[str]:
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return []
    return [s[:300] for x in v if (s := str(x).strip()) and not _is_placeholder(s)][:12]


def _norm_candidate(c: dict) -> dict | None:
    """Coerce one candidate assessment; drop it if it carries no assessment text."""
    # Live llava fills "decide" with bare strings instead of objects often enough that
    # assuming a dict here turned a usable read-out into a 502. Drop the malformed
    # entry and keep whatever else parsed — degrade, never raise.
    if not isinstance(c, dict):
        return None
    assessment = str(c.get("assessment") or "").strip()[:240]
    if not assessment or _is_placeholder(assessment):
        return None
    return {
        "assessment": assessment,
        "confidence": _conf(c.get("confidence")),
        "why": str(c.get("why") or "").strip()[:400],
    }


def interpret(image_b64: str, media_type: str = "image/jpeg") -> dict:
    """Run vision-LLM IMINT interpretation. Returns a structured OODA trace + best
    assessment, or {available: False, reason} when no vision model can serve it."""
    if not llm.available():
        return {"available": False, "reason": "No LLM/vision model is configured or reachable.",
                "scope": SCOPE_NOTE}

    try:
        result = llm.complete_vision(
            system=_SYSTEM, user=_USER, image_b64=image_b64,
            media_type=media_type, max_tokens=1200, json_mode=True,
        )
    except llm.BudgetExceeded as exc:
        return {"available": False, "reason": f"LLM unavailable: {exc}", "scope": SCOPE_NOTE}
    except Exception as exc:  # noqa: BLE001 — includes a text-only local model rejecting the image
        logger.warning("Vision IMINT call failed: %s", exc)
        return {
            "available": False,
            "reason": "The active model can't read images. Enable Claude vision, or set "
                      "a multimodal local model (e.g. llava, llama3.2-vision).",
            "scope": SCOPE_NOTE,
        }

    try:
        data = json.loads(_clean_json(result.text))
    except (json.JSONDecodeError, ValueError):
        # llava truncates long outputs mid-string under the token ceiling; salvage the
        # complete prefix rather than discarding minutes of CPU vision work.
        data = llm.salvage_truncated_json(result.text)
        if data is None:
            logger.warning("Vision IMINT returned unparseable JSON: %r", result.text[:200])
            return {"available": False, "reason": "The model did not return a usable assessment.",
                    "scope": SCOPE_NOTE}

    if not isinstance(data, dict):
        return {"available": False, "reason": "The model did not return a usable assessment.",
                "scope": SCOPE_NOTE}

    decide = data.get("decide")
    candidates = [nc for c in (decide if isinstance(decide, list) else []) if (nc := _norm_candidate(c))]
    # "act" arrives as a bare string when the model ignores the schema; anything but a
    # dict is treated as absent rather than crashing the tag lookups below.
    act = data.get("act") if isinstance(data.get("act"), dict) else {}
    best = _norm_candidate(act) or (candidates[0] if candidates else None)
    if best is None:
        return {"available": False, "reason": "No usable assessment could be inferred from the image.",
                "scope": SCOPE_NOTE}
    if not candidates:
        candidates = [best]
    # Carry the extra "act" tags onto the headline assessment when present.
    best = {
        **best,
        "facility_type": str(act.get("facility_type") or "").strip()[:80],
        "activity": str(act.get("activity") or "").strip()[:160],
    }

    return {
        "available": True,
        "discipline": "IMINT",
        "trace": {
            "observe": _strings(data.get("observe")),
            "orient": _strings(data.get("orient")),
            "decide": candidates,
        },
        "best": best,
        "scope": SCOPE_NOTE,
        "provider": result.provider,
        "cost_usd": round(result.cost_usd, 6),
    }
