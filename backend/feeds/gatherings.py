"""Public gatherings — keyless, from Wikidata.

The deck used to state, in as many words, that "public gatherings and festivals are
not covered: there is no keyless source for them". That was measured and found to be
wrong. Two Wikidata approaches were tried:

  • by CLASS (`?item wdt:P31/wdt:P279* wd:Q132241`) — unusable. The festival subclass
    tree leaks into Japanese shrine entries, and only 2 of 40 rows carried any
    recurrence date.
  • by DATE, with a location hop — works. Filtering on a start date inside a forward
    window and taking the coordinate from the event, its P276 location, or its P1001
    jurisdiction yields 40/40 rows with real coordinates: the 2026 Badminton World
    Championships in Delhi, the Mediterranean Games in Taranto, the Women's FIH Hockey
    World Cup in Amsterdam.

That is exactly the thing a security team needs for duty of care: a dated, located
crowd near an office. Sport and civic events dominate, which is the correct bias —
a stadium event is a mass-gathering risk in a way an obscure village fête is not.

Keyless and $0: the Wikidata Query Service needs no token, only a descriptive
User-Agent (they rate-limit anonymous hammering, so this is polled on the calendar
path, not per request).

Honest degradation: any failure returns [] and the caller says "not checked" rather
than rendering an empty calendar as "no gatherings", which would be the same lie the
holiday layer was fixed for.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "the-narrative-osint/0.2 (+https://thenarrative.io)"

# Event classes worth treating as a mass gathering. Deliberately narrow: these are
# the classes whose members reliably carry a date AND a venue.
_CLASSES = (
    "wd:Q132241",    # festival
    "wd:Q1656682",   # event
    "wd:Q13406554",  # sports competition
    "wd:Q464980",    # sporting event / tournament edition
    "wd:Q27968055",  # recurrent event edition
)

_QUERY = """
SELECT ?item ?itemLabel ?coord ?countryLabel ?start WHERE {{
  VALUES ?cls {{ {classes} }}
  ?item wdt:P31/wdt:P279* ?cls .
  ?item wdt:P580|wdt:P585 ?start .
  FILTER(?start >= "{start}"^^xsd:dateTime && ?start <= "{end}"^^xsd:dateTime)
  {{ ?item wdt:P625 ?coord }} UNION
  {{ ?item wdt:P276 ?loc . ?loc wdt:P625 ?coord }} UNION
  {{ ?item wdt:P1001 ?loc2 . ?loc2 wdt:P625 ?coord }}
  OPTIONAL {{ ?item wdt:P17 ?country . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT {limit}
"""


def build_query(days: int, limit: int, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    return _QUERY.format(
        classes=" ".join(_CLASSES),
        start=now.strftime("%Y-%m-%dT00:00:00Z"),
        end=end.strftime("%Y-%m-%dT00:00:00Z"),
        limit=limit,
    )


def parse_point(value: str | None) -> tuple[float, float] | None:
    """WKT 'Point(lng lat)' → (lat, lng). Returns None rather than a wrong coordinate."""
    if not value or not value.startswith("Point("):
        return None
    try:
        lng, lat = value[6:].rstrip(")").split()
        return float(lat), float(lng)
    except (ValueError, TypeError):
        return None


def parse_response(payload: dict) -> list[dict]:
    """SPARQL JSON → gatherings, deduplicated.

    The UNION over three location paths and the optional country make Wikidata return
    the same event several times (one row per binding combination), so rows are folded
    on (name, date) — otherwise one tournament would look like five separate crowds
    and inflate whatever counts them.
    """
    try:
        rows = payload["results"]["bindings"]
    except (KeyError, TypeError):
        return []
    seen: dict[tuple[str, str], dict] = {}
    for b in rows:
        name = (b.get("itemLabel", {}).get("value") or "").strip()
        start = (b.get("start", {}).get("value") or "")[:10]
        point = parse_point(b.get("coord", {}).get("value"))
        if not name or not start or not point:
            continue
        # A bare Q-id means Wikidata had no English label; a numbered placeholder on a
        # security deck is noise, not information.
        if name.startswith("Q") and name[1:].isdigit():
            continue
        key = (name.lower(), start)
        if key in seen:
            continue
        seen[key] = {
            "name": name,
            "date": start,
            "lat": point[0],
            "lng": point[1],
            "country": (b.get("countryLabel", {}).get("value") or "").strip() or None,
            "source": "wikidata",
        }
    return sorted(seen.values(), key=lambda g: (g["date"], g["name"]))


# The subclass walk (P279*) is genuinely expensive at Wikidata's end — measured at
# well over the 30s a page load can wait — so the answer is cached hard and shared by
# every request. The set changes on the order of days, not seconds.
_TTL = 6 * 3600
_TIMEOUT = 75
_CACHE: dict[int, tuple[float, list[dict]]] = {}


def reset_cache() -> None:
    _CACHE.clear()


async def fetch_gatherings(days: int = 60, limit: int = 300) -> list[dict] | None:
    """Dated, geolocated public gatherings starting within `days`.

    Returns None — NOT [] — when the source could not be reached, so the caller can
    say "not checked" instead of rendering a failed fetch as "no gatherings near your
    offices". An empty list is a real answer; None is the absence of one.
    """
    import time

    import httpx

    hit = _CACHE.get(days)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]

    query = build_query(days, limit)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
        }) as client:
            resp = await client.get(ENDPOINT, params={"query": query, "format": "json"})
            if resp.status_code >= 400:
                logger.warning("gatherings: wikidata returned %s", resp.status_code)
                return None
            out = parse_response(resp.json())
    except Exception as exc:  # noqa: BLE001 — a missing layer must never sink the page
        logger.warning("gatherings: fetch failed (%s): %s", type(exc).__name__, exc)
        return None
    _CACHE[days] = (time.time(), out)
    return out
