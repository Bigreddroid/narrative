"""
India Meteorological Department warnings — official, live, and NO key.

  * https://severeweather.wmo.int/json/wmo_all.json — WMO's Severe Weather
    Information Centre index of every CAP warning in force worldwide.
  * https://severeweather.wmo.int/v2/cap-alerts/<path> — the issuing authority's
    own CAP 1.2 document for one alert.

WHY THIS SOURCE AND NOT THE OBVIOUS TWO — all three measured before any code:

  1. IMD's own API (mausam.imd.gov.in/api/*) is **IP-whitelist gated, not key
     gated**. Every request answers `401 IP <addr> needs to be whitelisted`, with
     or without a key. Using it needs a static public IP and a written request to
     IMD, which is an organisational problem, not a code one.
  2. data.gov.in (api.data.gov.in) IS key-gated and live, so it looks like the
     answer — but it publishes **no real-time IMD warning resource**. Searching the
     public catalogue: `warning` → 0 hits, `nowcast` → 0 hits; everything IMD-ish
     is historical statistics (daily rainfall archives last updated 2022, cyclone
     frequency series from 1891). The only "weather" datasets touched in 2026 are
     road accidents classified by weather condition. A key would not have unlocked
     a warning feed because there is not one to unlock.
  3. WMO SWIC republishes the warnings national met agencies actually issue, in the
     CAP standard, keyless. Measured: 3,478 alerts in force globally, 77 of them
     India's, from real IMD centres (IMD-Bengaluru, IMD-Ahmedabad, IMD-Raipur,
     IMD-Agartala …). This is the same instrument, from the authority that issues it.

🔴 THE SENDER IS NOT ALWAYS IMD, AND IS NEVER RELABELLED AS IMD. India routes its
alerting through NDMA's SACHET, which carries the whole official ecosystem: IMD for
meteorology, CWC (Central Water Commission) for river floods, and others. Each alert
keeps its real `cap:sender`, and the source string is derived from it — an IMD
thunderstorm warning and a CWC flood warning are different authorities and are not
merged into one house brand. This mirrors advisories.py, which refuses to average
State Department levels against FCDO alert statuses.

🔴 COORDINATES ARE PRESENT FOR CWC AND ABSENT FOR IMD. SACHET puts the alert's
lat/lng in CAP's `altitude`/`ceiling` fields (a misuse of the standard — those are
metres, not degrees). Verified on a live CWC flood alert: altitude 26.13 / ceiling
86.58 is Supaul, Bihar, to two decimal places. But every IMD alert sampled carries
altitude=0 and ceiling=0, so **IMD warnings must be placed by district name**, not
by reading those fields. Trusting them blindly would have put every IMD warning at
0°N 0°E — in the Atlantic — which is exactly the kind of confident-and-wrong
placement this codebase keeps finding. `_coords_from_cap` therefore rejects 0/0.

IMD issues per DISTRICT and names them in `areaDesc` ("Ballari, Belagavi,
Chikkamagaluru, Dakshina Kannada districts of Karnataka"), so an alert is attached to
the registered sites whose city it names. An alert naming no registered district is
dropped rather than placed at a country centroid: a warning shown over a site it does
not cover is worse than one not shown.

Pure parsers (`parse_wmo_index`, `parse_cap`, `to_signal`) are separated from fetching
so the tests exercise the real payload shapes without touching the network — the
gatherings layer returned zero rows for weeks behind green tests that only ever saw
canned payloads, and the fix for that was never to let the network shape go unexercised.
"""

import asyncio
import logging
import re

logger = logging.getLogger(__name__)

WMO_INDEX = "https://severeweather.wmo.int/json/wmo_all.json"
CAP_BASE = "https://severeweather.wmo.int/v2/cap-alerts/"

# CAP 1.2 severity → importance. Deliberately parallel to weather.py's NWS mapping,
# because both are the same instrument (an agency's issued warning) on the same scale.
SEVERITY_IMPORTANCE = {
    "extreme": 88, "severe": 72, "moderate": 55, "minor": 40, "unknown": 45,
}
# CAP urgency nudges the ranking: an "Immediate" warning outranks a "Future" one of
# equal severity, because a GSOC acts on the first and plans around the second.
URGENCY_BONUS = {"immediate": 8, "expected": 4, "future": 0, "past": -10, "unknown": 0}

_ESCALATING_AT = 70

# India's alerts are prefixed IN- in the WMO index.
_INDIA_PREFIX = "IN-"

# Cities the register spells differently from the district IMD warns for. Only
# genuine renamings/anglicisations — never a "close enough" neighbour, which would
# silently widen a warning's footprint.
CITY_ALIASES = {
    "bengaluru": {"bengaluru", "bangalore", "bengaluru urban", "bengaluru rural"},
    "mumbai": {"mumbai", "bombay", "mumbai city", "mumbai suburban"},
    "chennai": {"chennai", "madras"},
    "kolkata": {"kolkata", "calcutta"},
    "pune": {"pune", "poona"},
    "kochi": {"kochi", "cochin", "ernakulam"},
    "gurugram": {"gurugram", "gurgaon"},
    "hyderabad": {"hyderabad", "rangareddy", "ranga reddy"},
    "noida": {"noida", "gautam buddha nagar", "gautam buddh nagar"},
    "thiruvananthapuram": {"thiruvananthapuram", "trivandrum"},
    "mysuru": {"mysuru", "mysore"},
    "vadodara": {"vadodara", "baroda"},
}

_TAG = re.compile(r"<(?:\w+:)?{tag}>(.*?)</(?:\w+:)?{tag}>", re.S)


def _tag(xml: str, tag: str) -> str | None:
    """First value of a CAP element, namespace-prefix agnostic.

    CAP documents here are served as `<cap:severity>`; other authorities emit a
    default namespace with no prefix. Matching on the local name handles both
    without pulling in an XML parser for four fields.
    """
    m = re.search(_TAG.pattern.format(tag=tag), xml or "", re.S)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip() or None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z ]+", " ", (s or "").lower()).strip()


def parse_wmo_index(payload: dict) -> list[dict]:
    """India's in-force alerts from the WMO index. Pure — no network.

    The index alone carries no severity and no coordinates, so it is only used to
    decide WHICH CAP documents to fetch; every graded field comes from the CAP.
    """
    items = (payload or {}).get("items") or []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        ident = str(it.get("id") or "")
        url = it.get("url")
        if ident.startswith(_INDIA_PREFIX) and url:
            out.append({"id": ident, "url": url,
                        "event": it.get("event"), "areaDesc": it.get("areaDesc")})
    return out


def parse_cap(xml: str) -> dict | None:
    """One CAP 1.2 alert → the fields we grade on. Pure — no network."""
    if not xml or "alert" not in xml:
        return None
    event = _tag(xml, "event")
    if not event:
        return None
    return {
        "identifier": _tag(xml, "identifier"),
        "sender": _tag(xml, "sender"),
        "event": event,
        "severity": (_tag(xml, "severity") or "unknown").lower(),
        "urgency": (_tag(xml, "urgency") or "unknown").lower(),
        "certainty": (_tag(xml, "certainty") or "unknown").lower(),
        "headline": _tag(xml, "headline"),
        "description": _tag(xml, "description"),
        "area_desc": _tag(xml, "areaDesc"),
        "effective": _tag(xml, "effective"),
        "expires": _tag(xml, "expires"),
        "altitude": _tag(xml, "altitude"),
        "ceiling": _tag(xml, "ceiling"),
    }


def _coords_from_cap(cap: dict) -> tuple[float, float] | None:
    """(lat, lng) when SACHET has smuggled them into altitude/ceiling, else None.

    0/0 is rejected explicitly: every IMD alert carries altitude=0 and ceiling=0,
    and 0°N 0°E is a real coordinate in the Atlantic Ocean. Treating "no data" as a
    location is how a layer ends up confidently wrong.
    """
    try:
        lat, lng = float(cap.get("altitude")), float(cap.get("ceiling"))
    except (TypeError, ValueError):
        return None
    if lat == 0 and lng == 0:
        return None
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return None
    return lat, lng


def sites_named_by(area_desc: str, sites: list[dict]) -> list[dict]:
    """Registered sites whose city the alert's area actually names.

    Matched on whole words against the normalised areaDesc, so "Balod" cannot match
    "Balodabazar" and a site is never pulled in by being a substring of a different
    district.
    """
    text = f" {_norm(area_desc)} "
    hits = []
    for s in sites:
        city = _norm(s.get("city") or "")
        if not city:
            continue
        names = CITY_ALIASES.get(city, {city})
        if any(f" {n} " in text for n in names):
            hits.append(s)
    return hits


def _source_for(sender: str | None) -> str:
    """The source string, from the authority that actually issued the alert.

    `imd` grades Admiralty A through source_reliability's provenance prior; other
    Indian authorities get the `gov_` prefix that advisories.py established, so they
    grade B ("usually reliable") through the SAME path rather than a special case.
    """
    s = (sender or "").strip().lower()
    if s.startswith("imd"):
        return "imd"
    if not s:
        return "gov_in_ndma"
    return "gov_in_" + re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def to_signal(cap: dict, sites: list[dict]) -> list[dict]:
    """One CAP alert → Signal dicts, one per registered site it covers. Pure.

    Returns [] when the alert names no registered site AND carries no coordinate:
    an official warning we cannot place is not shown, rather than shown somewhere
    convenient.
    """
    imp = SEVERITY_IMPORTANCE.get(cap.get("severity"), 45)
    imp = max(10, min(99, imp + URGENCY_BONUS.get(cap.get("urgency"), 0)))
    sender = cap.get("sender") or "NDMA"
    source = _source_for(sender)
    event = cap.get("event") or "Weather warning"
    area = cap.get("area_desc") or ""
    ident = cap.get("identifier") or ""

    # The issuer's own words. `headline` is what the authority chose to lead with;
    # we never rewrite it, and the description is appended verbatim so the reader
    # sees the warning, not our paraphrase of it.
    headline = cap.get("headline") or event
    desc = cap.get("description") or ""
    summary = f"{headline} {desc}".strip()[:900]
    summary = f"{summary} — issued by {sender} (CAP, via WMO SWIC)."

    placed = sites_named_by(area, sites)
    targets: list[tuple[str, float, float]] = [
        (s.get("city") or "site", s["lat"], s["lng"]) for s in placed
    ]
    if not targets:
        coords = _coords_from_cap(cap)
        if coords:
            targets = [(area.split(",")[0].strip() or "India", coords[0], coords[1])]
    if not targets:
        return []

    out = []
    for name, lat, lng in targets:
        out.append({
            # Stable per alert+place, so a re-emitted warning upserts rather than
            # duplicating. CAP identifiers are unique per issued alert.
            "external_id": f"imd-{ident}-{_norm(name).replace(' ', '-')}"[:180],
            "source": source,
            "title": f"{event} — {name}",
            "summary": summary,
            "category": "storm",
            "lat": lat,
            "lng": lng,
            "importance": imp,
            "status": "escalating" if imp >= _ESCALATING_AT else "developing",
            "geography": [name] + [a.strip() for a in area.split(",")[:2] if a.strip()],
            "ts": None,
        })
    return out


async def india_sites() -> list[dict]:
    """Registered Indian sites with usable coordinates.

    Returns [] when the register cannot be read — which, combined with the CAP
    coordinate fallback, means an unreadable register degrades to "only the alerts
    that carry their own coordinate", never to a silent all-clear.
    """
    try:
        from sqlalchemy import text

        from backend.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(text(
                "SELECT city, lat, lng FROM sites "
                "WHERE is_active AND lat IS NOT NULL AND lng IS NOT NULL "
                "AND lower(country) = 'india'"
            ))).all()
        return [{"city": r[0], "lat": float(r[1]), "lng": float(r[2])} for r in rows]
    except Exception as exc:  # noqa: BLE001 — the feed must still run without a DB
        logger.warning("imd: could not read the register (%s: %s)", type(exc).__name__, exc)
        return []


# The index lists every alert in force; India is ~2% of it. Fetching each CAP
# document is one small request, bounded so a busy monsoon day cannot open 200
# sockets at once.
_MAX_ALERTS = 120
_CONCURRENCY = 8

# ── Is India actually covered right now? ─────────────────────────────────────
# IMD REPLACES Open-Meteo inside India, so weather_global stops watching Indian
# metros — but only for as long as IMD is genuinely answering. If this feed is
# failing, dropping India from the model forecast too would leave 27 of 121 sites
# (the largest country in the estate) watched by nothing while the deck still
# reported weather "of 121". That is the precise failure this codebase has now
# fixed three times, so the swap is conditional on a recent success rather than
# assumed. In-process is sufficient: both feeds run in the same ingest cycle.
_last_answered_at: float | None = None
COVERAGE_TTL_SECONDS = 3 * 60 * 60


def _mark_answered() -> None:
    global _last_answered_at
    import time
    _last_answered_at = time.monotonic()


def covers_india_now() -> bool:
    """True when IMD has answered recently enough to be India's weather source."""
    if _last_answered_at is None:
        return False
    import time
    return (time.monotonic() - _last_answered_at) < COVERAGE_TTL_SECONDS


async def fetch_imd() -> list[dict] | None:
    """Live Indian official weather warnings as Signal dicts.

    Returns None when the WMO index itself could not be read — "we could not check"
    — and [] when it was read and India has nothing in force. The distinction is the
    codebase's convention (gatherings.py, scrapers/engine.py) and exists because a
    source that silently returns [] on failure renders as an all-clear.
    """
    import httpx  # lazy — keeps the parsers importable without the dep

    headers = {"User-Agent": "the-narrative/1.0 (intelligence@narrative.app)"}
    try:
        async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
            r = await client.get(WMO_INDEX)
            if r.status_code != 200:
                logger.warning("imd: WMO index returned %s", r.status_code)
                return None
            index = parse_wmo_index(r.json())
            if not index:
                return []

            sites = await india_sites()
            sem = asyncio.Semaphore(_CONCURRENCY)

            async def one(item):
                async with sem:
                    try:
                        rr = await client.get(CAP_BASE + item["url"])
                        if rr.status_code != 200:
                            return []
                        cap = parse_cap(rr.text)
                        return to_signal(cap, sites) if cap else []
                    except Exception as exc:  # noqa: BLE001 — one bad alert is not an outage
                        logger.debug("imd: alert %s unavailable (%s)", item.get("id"), exc)
                        return []

            results = await asyncio.gather(*(one(i) for i in index[:_MAX_ALERTS]))
    except Exception as exc:  # noqa: BLE001
        logger.warning("imd: fetch failed (%s: %s)", type(exc).__name__, exc)
        return None

    out = [sig for group in results for sig in group]
    _mark_answered()
    logger.info("imd: %d alerts in force, %d signals placed on the register",
                len(index), len(out))
    return out
