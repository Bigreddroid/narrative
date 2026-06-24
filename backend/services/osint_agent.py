"""
OSINT triage agent — turns a noisy open-source post into a structured Signal, or drops it.

This is the platform's first autonomous product agent: it reasons over an open-source
item to decide (a) is this a real, consequential world event? (b) what / where / how
important? It runs on the FREE local LLM (backend/services/llm.py). When no LLM is
available it degrades to a keyword heuristic, so OSINT ingest still works at $0 with no
model — matching the platform's free-first / graceful-degrade posture.

Geolocation uses a keyless country-centroid gazetteer first, then Nominatim, with an
in-process cache (Nominatim asks for ≤1 req/s). Unresolvable locations ingest as
non-geo (no map marker). Output category is constrained to synthesize.SECTOR_MAP keys
so the deterministic consequence engine can map it unchanged.
"""

import json
import logging
import re

from backend.feeds.synthesize import SECTOR_MAP

logger = logging.getLogger(__name__)

SOURCE = "osint_reddit"
ALLOWED_CATEGORIES = set(SECTOR_MAP.keys())  # disaster, conflict, unrest, cyber, ...
_DEFAULT_CATEGORY = "unrest"  # geopolitical catch-all that maps cleanly in SECTOR_MAP
_MIN_CONFIDENCE = 0.4         # below this, treat as not-relevant noise

_SYSTEM = (
    "You are an OSINT triage analyst for a world-consequence intelligence platform. "
    "Given a social-media post, decide whether it reports a REAL, consequential, "
    "real-world event (armed conflict, attack, disaster, natural hazard, civil unrest, "
    "sanctions, major cyber incident, market shock). Opinion, memes, analysis, history, "
    "domestic partisan politics, and rumor are NOT relevant. "
    "Respond with ONLY a JSON object with keys: "
    "relevant (bool), category (one of: " + ", ".join(sorted(ALLOWED_CATEGORIES)) + "), "
    "title (short neutral headline), summary (one sentence), "
    "location_name (most specific place, or empty string), "
    "importance (integer 0-100), confidence (float 0-1). No prose."
)

# Keyword → category for the no-LLM heuristic fallback (and a quick relevance gate).
_KEYWORDS = [
    (("earthquake", "magnitude", "aftershock"), "disaster"),
    (("wildfire", "bushfire"), "wildfire"),
    (("hurricane", "typhoon", "cyclone", "storm surge"), "storm"),
    (("flood", "flooding", "inundat"), "flood"),
    (("drought",), "drought"),
    (("volcano", "eruption", "ashfall"), "volcano"),
    (("missile", "airstrike", "shelling", "offensive", "frontline", "drone strike",
      "invasion", "ceasefire", "troops", "war"), "conflict"),
    (("protest", "riot", "unrest", "coup", "clashes", "crackdown"), "unrest"),
    (("sanction", "embargo", "export ban"), "sanction"),
    (("ransomware", "data breach", "cyberattack", "hacked", "malware"), "cyber"),
    (("default", "currency", "inflation", "stock market", "oil price"), "market"),
]

# Coarse country centroids (lat, lng) — keyless fast path for the common hot spots.
_COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "ukraine": (48.4, 31.2), "russia": (61.5, 105.3), "israel": (31.0, 34.8),
    "gaza": (31.4, 34.4), "palestine": (31.9, 35.2), "lebanon": (33.9, 35.5),
    "iran": (32.4, 53.7), "iraq": (33.2, 43.7), "syria": (34.8, 38.9),
    "yemen": (15.6, 48.0), "sudan": (12.9, 30.2), "china": (35.9, 104.2),
    "taiwan": (23.7, 121.0), "india": (22.0, 79.0), "pakistan": (30.4, 69.3),
    "united states": (39.8, -98.6), "usa": (39.8, -98.6), "myanmar": (21.9, 95.9),
    "north korea": (40.3, 127.5), "south korea": (36.5, 127.8), "afghanistan": (33.9, 67.7),
    "ethiopia": (9.1, 40.5), "venezuela": (6.4, -66.6), "france": (46.6, 2.2),
    "germany": (51.2, 10.4), "united kingdom": (54.0, -2.0), "turkey": (39.0, 35.2),
}

_GEO_CACHE: dict[str, tuple[float | None, float | None]] = {}


def geocode(name: str) -> tuple[float | None, float | None]:
    """Place name → (lat, lng), or (None, None). Cached; country centroid then Nominatim."""
    if not name:
        return (None, None)
    key = name.strip().lower()
    if key in _GEO_CACHE:
        return _GEO_CACHE[key]
    for country, latlng in _COUNTRY_CENTROIDS.items():
        if country in key:
            _GEO_CACHE[key] = latlng
            return latlng
    try:
        import httpx
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": name, "format": "json", "limit": 1},
            headers={"User-Agent": "the-narrative-osint/0.1 (+https://thenarrative.io)"},
            timeout=8.0,
        )
        arr = resp.json() if resp.status_code == 200 else []
        if arr:
            latlng = (float(arr[0]["lat"]), float(arr[0]["lon"]))
            _GEO_CACHE[key] = latlng
            return latlng
    except Exception:  # noqa: BLE001 — geocoding is best-effort; fall through to non-geo
        pass
    _GEO_CACHE[key] = (None, None)
    return (None, None)


def _signal(post: dict, category: str, title: str, summary: str,
            importance: int, confidence: float, location: str) -> dict:
    lat, lng = geocode(location) if location else (None, None)
    return {
        "external_id": post["external_id"],
        "source": SOURCE,
        "title": title.strip()[:300] or post["title"],
        "summary": summary.strip()[:600] or post["title"],
        "category": category,
        "lat": lat,
        "lng": lng,
        "importance": int(max(0, min(100, importance))),
        "status": "escalating" if importance >= 70 else "developing",
        "geography": [location] if location else [],
        "ts": int(post["created_utc"] * 1000) if post.get("created_utc") else None,
        "confidence": round(float(confidence), 2),
        "evidence_url": post.get("url") or "",
    }


def _heuristic_triage(post: dict) -> dict | None:
    """No-LLM fallback: keyword category match → Signal, else drop. Low confidence."""
    text = f"{post.get('title', '')} {post.get('selftext', '')}".lower()
    category = next((cat for kws, cat in _KEYWORDS if any(k in text for k in kws)), None)
    if not category:
        return None  # no event keyword ⇒ assume noise, don't pollute the feed
    location = next((c for c in _COUNTRY_CENTROIDS if c in text), "")
    importance = min(70, 45 + post.get("score", 0) // 200)
    return _signal(post, category, post["title"], post.get("title", ""),
                   importance, 0.3, location)


def _llm_triage(post: dict) -> dict | None:
    """LLM-driven triage via the free local model. Returns a Signal or None."""
    from backend.services import llm

    user = (f"SUBREDDIT: r/{post.get('subreddit', '')}\n"
            f"TITLE: {post.get('title', '')}\n"
            f"BODY: {post.get('selftext', '')[:1000]}")
    res = llm.complete(_SYSTEM, user, max_tokens=400, json_mode=True)
    try:
        data = json.loads(res.text)
    except (json.JSONDecodeError, TypeError):
        # Some local models wrap JSON in prose — salvage the first {...} block.
        m = re.search(r"\{.*\}", res.text or "", re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))

    if not data.get("relevant"):
        return None
    confidence = float(data.get("confidence") or 0.0)
    if confidence < _MIN_CONFIDENCE:
        return None
    category = str(data.get("category") or "").strip().lower()
    if category not in ALLOWED_CATEGORIES:
        category = _DEFAULT_CATEGORY
    return _signal(
        post,
        category,
        str(data.get("title") or post["title"]),
        str(data.get("summary") or post["title"]),
        int(data.get("importance") or 50),
        confidence,
        str(data.get("location_name") or "").strip(),
    )


def triage(post: dict, allow_llm: bool = True) -> dict | None:
    """Raw post → Signal dict, or None to drop. Synchronous (worker offloads via to_thread).

    Uses the LLM when allowed/available; on any LLM failure, or when disallowed, falls
    back to the keyword heuristic so OSINT ingest never hard-fails.
    """
    from backend.services import llm

    if allow_llm and llm.available():
        try:
            return _llm_triage(post)
        except Exception as exc:  # noqa: BLE001 — degrade to heuristic, never crash ingest
            logger.warning("OSINT LLM triage failed (%s); using heuristic", exc)
    return _heuristic_triage(post)
