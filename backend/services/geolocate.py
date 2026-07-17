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

Work through the OODA loop, filling each field with your OWN findings about THIS photo:
- observe: the concrete visual facts you actually see — readable sign text and its
  script/language, architecture style, vehicles and license-plate style, which side of
  the road traffic drives on, vegetation, terrain, sky/sun. State only what is visible.
- orient: geographic inferences, each tied to one observation above.
- decide: 2-4 ranked candidate locations (most likely first), each with real decimal
  coordinates and a one-sentence reason citing the evidence.
- act: your single best candidate, copied verbatim from the top "decide" entry
  (same place, country, lat, lng, confidence, and why).

Return VALID JSON ONLY (no markdown, no prose outside JSON) in exactly this shape, with
the empty strings and zeros replaced by your actual findings:
{
  "observe": [],
  "orient": [],
  "decide": [{"place": "", "country": "", "lat": 0.0, "lng": 0.0, "confidence": 0.0, "why": ""}],
  "act": {"place": "", "country": "", "lat": 0.0, "lng": 0.0, "confidence": 0.0, "why": ""}
}
Rules: use real decimal lat/lng. Be honest — if evidence is thin, say so in "why" and lower
the confidence. Never invent sign text you cannot actually read, and never echo these field
descriptions back as if they were observations."""

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
    # NOT _coord(..., 0, 1): llava answers this prompt in percent (confidence: 90.0),
    # which a range check discards — landing a correct pin at 0.0 confidence.
    return {
        "place": str(c.get("place") or "Unknown").strip()[:120],
        "country": str(c.get("country") or "").strip()[:80],
        "lat": lat,
        "lng": lng,
        "confidence": llm.normalize_confidence(c.get("confidence")),
        "why": str(c.get("why") or "").strip()[:400],
    }


# Substrings that signal a model echoed the schema's field guidance instead of
# reporting real findings; such items are dropped from the trace.
_PLACEHOLDER_MARKERS = (
    "concrete visual facts",
    "geographic inferences",
    "each tied to",
    "readable sign text, script",
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

    # Some models return "act" with coordinates but no confidence/why (or a blank place),
    # leaving the headline pin empty. Backfill those from the nearest decide candidate so
    # the best guess always carries its rationale.
    if best["confidence"] == 0.0 or not best["why"] or best["place"] == "Unknown":
        match = min(candidates, key=lambda c: (c["lat"] - best["lat"]) ** 2 + (c["lng"] - best["lng"]) ** 2)
        if not best["why"]:
            best["why"] = match["why"]
        if best["confidence"] == 0.0:
            best["confidence"] = match["confidence"]
        if best["place"] == "Unknown":
            best["place"], best["country"] = match["place"], match["country"] or best["country"]

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
