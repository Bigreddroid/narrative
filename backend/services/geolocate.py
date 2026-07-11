"""
Reverse-image geolocation via a vision-LLM, structured as a DANA-style OODA trace.

Given a photo, infer WHERE it was taken and — more importantly — show the reasoning
so a user can judge it (this is the honest counter to a black-box "map pin"). The
model is asked to reason in the Observe → Orient → Decide → Act loop:

  Observe — concrete visual facts (signage text, architecture, vehicles, flora, sky)
  Orient  — geographic inferences from those facts (language, hemisphere, climate…)
  Decide  — ranked candidate locations, each with lat/lng + why
  Act      — the single best pin: place, country, lat, lng, confidence

v1 is vision-LLM only (no GeoCLIP / embedding retrieval yet). It runs free on a
local multimodal Ollama model, or on Claude vision when paid APIs are enabled. If
no vision model can serve the request, it degrades to an honest "unavailable"
result rather than fabricating coordinates.
"""

import json
import logging

from backend.services import llm

logger = logging.getLogger(__name__)

_SYSTEM = """You are a forensic image geolocation analyst. You infer where a photo
was taken purely from visual evidence, and you SHOW YOUR WORK so a human can check it.

Reason in the OODA loop and return VALID JSON ONLY (no markdown, no prose outside JSON):
{
  "observe": ["concrete visual facts: readable sign text, script/language, architecture,
               vehicles + license-plate style, driving side, vegetation, terrain, sky/sun"],
  "orient":  ["geographic inferences drawn from the observations, each tied to a fact"],
  "decide":  [ {"place": "City/area", "country": "Country", "lat": <float>, "lng": <float>,
                "confidence": <0..1>, "why": "1 sentence citing the evidence"} ],
  "act":     {"place": "...", "country": "...", "lat": <float>, "lng": <float>,
              "confidence": <0..1>, "why": "why this is the single best guess"}
}
Rules: give 2-4 ranked candidates in "decide" (most likely first); "act" must equal the
top candidate. Use real decimal lat/lng. Be honest — if evidence is thin, say so in "why"
and lower the confidence. Never invent sign text you cannot actually read."""

_USER = ("Geolocate this photograph. Extract every usable geographic clue, reason step by "
         "step, and return the JSON schema exactly. Coordinates must be plausible decimals.")


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


def _coord(v, lo: float, hi: float):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if lo <= f <= hi else None


def _norm_candidate(c: dict) -> dict | None:
    """Coerce one candidate; drop it if it has no usable coordinate."""
    lat, lng = _coord(c.get("lat"), -90, 90), _coord(c.get("lng"), -180, 180)
    if lat is None or lng is None:
        return None
    conf = _coord(c.get("confidence"), 0, 1)
    return {
        "place": str(c.get("place") or "Unknown").strip()[:120],
        "country": str(c.get("country") or "").strip()[:80],
        "lat": lat,
        "lng": lng,
        "confidence": conf if conf is not None else 0.0,
        "why": str(c.get("why") or "").strip()[:400],
    }


def _strings(v) -> list[str]:
    if isinstance(v, list):
        return [str(x).strip()[:300] for x in v if str(x).strip()][:12]
    if isinstance(v, str) and v.strip():
        return [v.strip()[:300]]
    return []


def geolocate(image_b64: str, media_type: str = "image/jpeg") -> dict:
    """Run the vision-LLM geolocation. Returns a structured OODA trace + best pin,
    or {available: False, reason} when no vision model can serve the request."""
    if not llm.available():
        return {"available": False, "reason": "No LLM/vision model is configured or reachable."}

    try:
        result = llm.complete_vision(
            system=_SYSTEM, user=_USER, image_b64=image_b64,
            media_type=media_type, max_tokens=1200, json_mode=True,
        )
    except llm.BudgetExceeded as exc:
        return {"available": False, "reason": f"LLM unavailable: {exc}"}
    except Exception as exc:  # noqa: BLE001 — includes a text-only local model rejecting the image
        logger.warning("Vision geolocation call failed: %s", exc)
        return {
            "available": False,
            "reason": "The active model can't read images. Enable Claude vision, or set "
                      "a multimodal local model (e.g. llava, llama3.2-vision).",
        }

    try:
        data = json.loads(_clean_json(result.text))
    except (json.JSONDecodeError, ValueError):
        logger.warning("Vision geolocation returned unparseable JSON: %r", result.text[:200])
        return {"available": False, "reason": "The model did not return a usable location."}

    candidates = [nc for c in (data.get("decide") or []) if (nc := _norm_candidate(c))]
    best = _norm_candidate(data.get("act") or {}) or (candidates[0] if candidates else None)
    if best is None:
        return {"available": False, "reason": "No plausible location could be inferred from the image."}
    if not candidates:
        candidates = [best]

    return {
        "available": True,
        "trace": {
            "observe": _strings(data.get("observe")),
            "orient": _strings(data.get("orient")),
            "decide": candidates,
        },
        "best": best,
        "provider": result.provider,
        "cost_usd": round(result.cost_usd, 6),
    }
