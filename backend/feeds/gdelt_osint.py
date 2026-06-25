"""
GDELT OSINT — free, KEYLESS open-source news signal via the GDELT DOC 2.0 API.

This is the default OSINT candidate source. Reddit (backend/feeds/reddit_osint.py)
is kept wired but blocks both anonymous .json reads and app-credential creation, so
GDELT is the reliable keyless path: the DOC API works from datacenter IPs (unlike the
GEO 2.0 endpoint, which 404s — see hazard_ingest_worker) and needs no account.

The DOC API returns recent global news ARTICLES matching a conflict/disaster/unrest
query. Like Reddit posts these are NOISY, so parse_gdelt_doc only normalizes raw
candidates — the LLM triage agent (backend/services/osint_agent.py) decides relevance,
category, geolocation, and importance before a candidate becomes a NarrativeEvent.
The article title is the signal (the DOC API returns no body). Source = 'osint_gdelt'.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SOURCE = "osint_gdelt"
FEED_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = "the-narrative-osint/0.2 (+https://thenarrative.io)"

# Consequential-event themes. sourcelang:eng keeps the local LLM on familiar ground.
DEFAULT_QUERY = (
    "(airstrike OR missile OR offensive OR clashes OR coup OR insurgents OR earthquake "
    'OR "flash flood" OR wildfire OR cyclone OR eruption OR cyberattack OR ransomware '
    "OR sanctions OR explosion OR evacuation) sourcelang:eng"
)
_RETRY_BACKOFF_SECONDS = 6.0  # GDELT DOC throttles hard (~1 req / few s) → one backed-off retry


def _parse_seendate(s: str | None) -> float | None:
    """GDELT seendate 'YYYYMMDDTHHMMSSZ' → epoch seconds, or None."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, TypeError):
        return None


def parse_gdelt_doc(data: dict) -> list[dict]:
    """GDELT DOC ArtList JSON → list of raw post-candidate dicts (NOT yet Signals).

    Pure + testable: no I/O. Skips articles without a title or url, dedupes by url,
    and keeps English only. Output shape matches the Reddit candidate dicts so the
    same triage agent consumes both (title carries the signal; selftext is empty).
    """
    articles = (data or {}).get("articles") or []
    out: list[dict] = []
    seen: set[str] = set()
    for a in articles:
        title = (a.get("title") or "").strip()
        url = (a.get("url") or "").strip()
        if not title or not url or url in seen:
            continue
        lang = (a.get("language") or "").strip().lower()
        if lang and lang not in ("english", "en"):
            continue
        seen.add(url)
        pid = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        out.append({
            "external_id": f"gdelt-{pid}",
            # Source context shown to the triage LLM (where Reddit puts the subreddit).
            "subreddit": a.get("domain") or a.get("sourcecountry") or "news",
            "title": title,
            "selftext": "",  # DOC API returns no body — the headline is the signal
            "url": url,
            "score": 0,
            "num_comments": 0,
            "created_utc": _parse_seendate(a.get("seendate")),
        })
    return out


async def fetch_gdelt_osint(query: str = DEFAULT_QUERY, maxrecords: int = 75,
                            timespan: str = "1h") -> list[dict]:
    """Fetch recent matching articles → raw candidates. One backoff+retry on 429.

    Lazy-imports httpx so parse_gdelt_doc stays importable in tests without the dep.
    Returns [] on persistent failure (the worker treats an empty run as a no-op).
    """
    import httpx

    params = {"query": query, "mode": "ArtList", "format": "json",
              "maxrecords": maxrecords, "timespan": timespan, "sort": "DateDesc"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                 headers={"User-Agent": USER_AGENT}) as client:
        for attempt in (0, 1):
            resp = await client.get(FEED_URL, params=params)
            if resp.status_code == 429 and attempt == 0:
                logger.warning("GDELT DOC 429 (rate-limited) — backing off %.0fs and retrying once",
                               _RETRY_BACKOFF_SECONDS)
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
                continue
            resp.raise_for_status()
            return parse_gdelt_doc(resp.json())
    return []
