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

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "the-narrative-osint/0.2 (+https://thenarrative.io)"

# Event classes worth treating as a mass gathering. Deliberately narrow: these are
# the classes whose members reliably carry a date AND a venue.
#
# The set was widened after measuring, not guessing. Counting DISTINCT items that
# carry both a forward date (90d) and a resolvable coordinate, per class:
#
#     concert            Q182832      65
#     trade fair         Q57305        3
#     music festival     Q868557       2
#     wedding            Q49836        0
#     state funeral      Q1052001      0
#     demonstration      Q175331       0
#     strike             Q49776        0
#     marathon           Q40244        0
#     pilgrimage         Q1644573      0
#     rally              Q19609158     0
#     political rally    Q110455182    0
#     concert tour       Q1573906      0
#
# So the disruptive-but-unscheduled classes — a celebrity wedding, a protest, a
# strike, a marathon — are NOT available here. Wikidata records those after the
# fact, not as forward-dated located events, and adding their QIDs would have
# bought a longer class list and zero extra rows. They are left out rather than
# listed to look thorough; if they are wanted they need a different source, not a
# wider SPARQL query.
# wd:Q1656682 ("event") was dropped, not forgotten. It is the superclass of very
# nearly everything, so P279* over it is the walk that makes Wikidata give up: it
# returned 502/504 on every attempt, contributed zero rows, and cost ~50s of latency
# per refresh while doing it. Every useful member is reachable through the specific
# classes below.
_CLASSES = (
    "wd:Q132241",    # festival
    "wd:Q13406554",  # sports competition
    "wd:Q464980",    # sporting event / tournament edition
    "wd:Q27968055",  # recurrent event edition
    "wd:Q182832",    # concert            — measured +65
    "wd:Q868557",    # music festival     — measured +2
    "wd:Q57305",     # trade fair         — measured +3
)

# Matched class -> the word the board shows. Ordered most specific first: an item is
# usually an instance of several of these (a music festival is also a festival, which
# is also an event), and the deck was calling a baseball fixture a "festival" because
# whichever binding arrived first won. Lower index wins.
_KINDS = (
    ("Q182832", "concert"),
    ("Q868557", "music festival"),
    ("Q57305", "trade fair"),
    ("Q13406554", "sport"),
    ("Q464980", "sport"),
    ("Q132241", "festival"),
    ("Q27968055", "event"),
    ("Q1656682", "event"),
)
_KIND_RANK = {qid: i for i, (qid, _) in enumerate(_KINDS)}
_KIND_LABEL = dict(_KINDS)

# Rank by the LABEL too, for merging rows that came back from separate per-class
# queries. Labels repeat ("sport" appears twice), so the first — most specific —
# occurrence wins.
_LABEL_RANK: dict[str, int] = {}
for _i, (_q, _lab) in enumerate(_KINDS):
    _LABEL_RANK.setdefault(_lab, _i)


def label_rank(kind: str | None) -> int:
    """Specificity of a kind label; unknown sorts last."""
    return _LABEL_RANK.get(kind or "", len(_KINDS))


def classify(cls_uri: str | None) -> tuple[int, str]:
    """Wikidata class URI -> (specificity rank, label). Unknown sorts last as 'event'."""
    qid = (cls_uri or "").rsplit("/", 1)[-1]
    if qid in _KIND_RANK:
        return _KIND_RANK[qid], _KIND_LABEL[qid]
    return len(_KINDS), "event"

# ONE class per query, fanned out concurrently — NOT a single VALUES block over all
# of them. Measured: the combined query 504s at Wikidata after ~65s, and it does so on
# the ORIGINAL five classes too, so this layer was already dead in production and the
# deck was honestly reporting "not checked" over a source that could never answer.
# The subclass walk (P279*) is the expensive part and its cost compounds when several
# large trees are unioned; each class on its own returns comfortably.
#
# Splitting also fixes the bias the module docstring admitted to. With one shared
# LIMIT, sport crowded everything else out because it simply had the most rows; a
# per-class limit means a concert cannot be pushed off the board by a fixture list.
_QUERY = """
SELECT ?item ?itemLabel ?coord ?countryLabel ?start ?cls WHERE {{
  VALUES ?cls {{ {cls} }}
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


def build_query(days: int, limit: int, now: datetime | None = None,
                cls: str = "wd:Q13406554") -> str:
    now = now or datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    return _QUERY.format(
        cls=cls,
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
    rank: dict[tuple[str, str], int] = {}
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
        cls_rank, kind = classify(b.get("cls", {}).get("value"))
        if key in seen:
            # Same event, different class binding. Keep the most specific label rather
            # than whichever row Wikidata happened to return first.
            if cls_rank < rank[key]:
                seen[key]["kind"] = kind
                rank[key] = cls_rank
            continue
        rank[key] = cls_rank
        seen[key] = {
            "name": name,
            "date": start,
            "lat": point[0],
            "lng": point[1],
            "country": (b.get("countryLabel", {}).get("value") or "").strip() or None,
            "kind": kind,
            "source": "wikidata",
        }
    return sorted(seen.values(), key=lambda g: (g["date"], g["name"]))


# The subclass walk (P279*) is genuinely expensive at Wikidata's end — measured at
# well over the 30s a page load can wait — so the answer is cached hard and shared by
# every request. The set changes on the order of days, not seconds.
_TTL = 6 * 3600
_TIMEOUT = 75
_CACHE: dict[int, tuple[float, list[dict]]] = {}


# Requests that are currently refreshing the cache, so a burst of page loads on a
# cold cache sends ONE query to Wikidata rather than one per viewer.
_INFLIGHT: set[int] = set()
# Strong references to background refreshes: asyncio only holds a weak one, and a
# garbage-collected task cancels the refresh it was doing.
_TASKS: set = set()


def reset_cache() -> None:
    _CACHE.clear()
    _INFLIGHT.clear()


def cached(days: int) -> list[dict] | None:
    """The fresh cached answer, or None if there is none. Never fetches."""
    hit = _CACHE.get(days)
    return hit[1] if hit and time.time() - hit[0] < _TTL else None


async def _refresh(days: int, limit: int) -> None:
    try:
        await fetch_gatherings(days, limit)
    finally:
        _INFLIGHT.discard(days)


def gatherings_now(days: int = 60, limit: int = 300) -> list[dict] | None:
    """Cached gatherings if we have them; otherwise None, and a refresh is started.

    NEVER blocks. The SPARQL subclass walk is allowed 75 seconds (_TIMEOUT) because
    that is genuinely how long Wikidata can take, but the deck gives the whole
    calendar request 15 (api.js). Awaiting the fetch inline therefore did not just
    lose the gatherings layer on a cold cache — it blew the client timeout for the
    WHOLE response, so the live 43-country holiday layer went blank too, and the
    strip said "checked, nothing scoring" over both. A slow optional layer must not
    be able to take a working one down with it.

    Returning None here is the honest answer and the caller already renders it
    correctly: `gatherings_checked` is False, which reads "not checked yet" rather
    than "no crowds near you". The deck re-polls every 10 minutes and the warmed
    cache answers instantly from then on.
    """
    hit = cached(days)
    if hit is not None:
        return hit
    if days not in _INFLIGHT:
        _INFLIGHT.add(days)
        try:
            task = asyncio.create_task(_refresh(days, limit))
        except RuntimeError:  # no running loop (sync caller) — nothing to warm
            _INFLIGHT.discard(days)
            return None
        _TASKS.add(task)
        task.add_done_callback(_TASKS.discard)
    return None


async def fetch_gatherings(days: int = 60, limit: int = 300) -> list[dict] | None:
    """Dated, geolocated public gatherings starting within `days`.

    Returns None — NOT [] — when the source could not be reached, so the caller can
    say "not checked" instead of rendering a failed fetch as "no gatherings near your
    offices". An empty list is a real answer; None is the absence of one.
    """
    import httpx

    hit = cached(days)
    if hit is not None:
        return hit

    # Per-class limit. The old single LIMIT was a global budget the biggest class ate.
    per_class = max(20, limit // len(_CLASSES))

    async def one(client, cls: str) -> list[dict] | None:
        """Rows for a single class, or None if THIS class could not be answered."""
        try:
            resp = await client.get(ENDPOINT, params={
                "query": build_query(days, per_class, cls=cls), "format": "json",
            })
            if resp.status_code >= 400:
                logger.warning("gatherings: wikidata returned %s for %s", resp.status_code, cls)
                return None
            return parse_response(resp.json())
        except Exception as exc:  # noqa: BLE001
            logger.warning("gatherings: %s failed (%s): %s", cls, type(exc).__name__, exc)
            return None

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
        }) as client:
            results = await asyncio.gather(*(one(client, c) for c in _CLASSES))
    except Exception as exc:  # noqa: BLE001 — a missing layer must never sink the page
        logger.warning("gatherings: fetch failed (%s): %s", type(exc).__name__, exc)
        return None

    # Every class failed -> we did not check. Distinct from "checked, found nothing",
    # which is what an empty list means and is a legitimate answer.
    if all(r is None for r in results):
        logger.warning("gatherings: every class failed; reporting NOT CHECKED")
        return None

    failed = [c for c, r in zip(_CLASSES, results) if r is None]
    if failed:
        # Partial answers are still worth showing, but not silently: a half-checked
        # layer that looks fully checked is the failure mode this module exists to
        # avoid, so the gap is logged rather than smoothed over.
        logger.warning("gatherings: %d of %d classes failed (%s); result is partial",
                       len(failed), len(_CLASSES), ", ".join(failed))

    merged: dict[tuple[str, str], dict] = {}
    for rows in results:
        for gth in rows or []:
            key = (gth["name"].lower(), gth["date"])
            prev = merged.get(key)
            # Same event reached through two class queries — keep the more specific
            # label, matching the rule parse_response applies within one response.
            if prev is None or label_rank(gth["kind"]) < label_rank(prev["kind"]):
                merged[key] = gth
    out = sorted(merged.values(), key=lambda g: (g["date"], g["name"]))
    _CACHE[days] = (time.time(), out)
    return out
