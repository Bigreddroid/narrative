"""
RSS/Atom OSINT — free, KEYLESS multi-source open-source news collector.

This is the OSINT v2 sourcing increment: a portfolio of feeds so no single
blocked source (Reddit's anon .json, GDELT's throttling) can starve ingestion.
It reads ordinary RSS 2.0 and Atom feeds — Google News search RSS, Reddit's
per-subreddit `.rss` (Atom, less aggressively bot-blocked than `.json`), and any
publisher feed — using only the Python stdlib XML parser (no feedparser dep), so
parse_rss stays pure + testable and the $0/no-dep posture holds.

Like the other OSINT feeds these items are NOISY: parse_rss only normalizes raw
post candidates into the shared candidate shape (matching gdelt_osint /
osint_threatintel), and the LLM triage agent (backend/services/osint_agent.py) decides
relevance, category, geolocation, and importance before a candidate becomes a
NarrativeEvent. The headline carries the signal; the feed summary fills selftext.
Source = 'osint_rss'.
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

SOURCE = "osint_rss"
USER_AGENT = "the-narrative-osint/0.2 (+https://thenarrative.io)"

# Default keyless feed portfolio: (url, source-context label). Google News search
# RSS covers the consequential-event themes; Reddit's .rss is the keyless social
# path that survives where .json 403s. Override via settings.osint_rss_feeds.
_GOOGLE_NEWS_Q = (
    "airstrike OR missile OR offensive OR clashes OR coup OR earthquake OR "
    '"flash flood" OR wildfire OR cyclone OR eruption OR cyberattack OR '
    "ransomware OR sanctions OR explosion OR evacuation"
)
# Second Google News query aimed at economic / supply-chain consequence themes,
# complementing the conflict/hazard query above (kept separate so one query's
# throttling can't drop the other's coverage).
_GOOGLE_NEWS_ECON_Q = (
    'strait OR chokepoint OR blockade OR "port strike" OR "export ban" OR '
    "tariff OR embargo OR semiconductor OR chip OR pipeline OR "
    '"supply chain" OR default OR devaluation OR shortage'
)
DEFAULT_FEEDS: list[tuple[str, str]] = [
    (f"https://news.google.com/rss/search?q={_GOOGLE_NEWS_Q}&hl=en-US&gl=US&ceid=US:en",
     "news.google.com"),
    (f"https://news.google.com/rss/search?q={_GOOGLE_NEWS_ECON_Q}&hl=en-US&gl=US&ceid=US:en",
     "news.google.com/econ"),
    ("https://www.reddit.com/r/worldnews/.rss", "reddit/worldnews"),
    ("https://www.reddit.com/r/CredibleDefense/.rss", "reddit/CredibleDefense"),
    ("https://www.reddit.com/r/geopolitics/.rss", "reddit/geopolitics"),
]

_ATOM = "{http://www.w3.org/2005/Atom}"
# Strip HTML tags out of feed summaries so the triage LLM sees clean text.
_TAG_RE = re.compile(r"<[^>]+>")


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def _strip_html(s: str) -> str:
    return _TAG_RE.sub(" ", s or "").replace("&nbsp;", " ").strip()


def _parse_date(s: str | None) -> float | None:
    """RSS RFC-822 or Atom RFC-3339 date string → epoch seconds, or None."""
    if not s:
        return None
    s = s.strip()
    try:  # RSS 2.0: 'Tue, 10 Jun 2026 14:30:00 GMT'
        dt = parsedate_to_datetime(s)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
    except (TypeError, ValueError):
        pass
    try:  # Atom: '2026-06-10T14:30:00Z'
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (TypeError, ValueError):
        return None


def _atom_link(entry) -> str:
    """Atom <link href=...> — prefer rel='alternate'/no-rel over 'self'."""
    best = ""
    for link in entry.findall(f"{_ATOM}link"):
        href = (link.get("href") or "").strip()
        if not href:
            continue
        rel = (link.get("rel") or "alternate").strip()
        if rel == "alternate":
            return href
        best = best or href
    return best


def parse_rss(xml_text: str, source_label: str = "rss") -> list[dict]:
    """RSS 2.0 or Atom XML → list of raw post-candidate dicts (NOT yet Signals).

    Pure + testable: no I/O. Auto-detects RSS vs Atom, skips items without a title
    or link, and dedupes by link within the feed. Output shape matches the Reddit /
    GDELT candidate dicts so the same triage agent consumes all three.
    """
    try:
        root = ET.fromstring((xml_text or "").strip())
    except ET.ParseError:
        return []

    out: list[dict] = []
    seen: set[str] = set()

    # RSS 2.0: <rss><channel><item>... ; Atom: <feed><entry>...
    items = root.findall(".//item")
    is_atom = not items
    if is_atom:
        items = root.findall(f".//{_ATOM}entry")

    for it in items:
        if is_atom:
            title = _text(it.find(f"{_ATOM}title"))
            link = _atom_link(it)
            summary = _strip_html(_text(it.find(f"{_ATOM}summary"))
                                  or _text(it.find(f"{_ATOM}content")))
            date = (_text(it.find(f"{_ATOM}published"))
                    or _text(it.find(f"{_ATOM}updated")))
        else:
            title = _text(it.find("title"))
            link = _text(it.find("link"))
            summary = _strip_html(_text(it.find("description")))
            date = _text(it.find("pubDate"))

        title = title.strip()
        link = link.strip()
        if not title or not link or link in seen:
            continue
        seen.add(link)
        pid = hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]
        out.append({
            "external_id": f"rss-{pid}",
            # Source context shown to the triage LLM (where Reddit puts the subreddit).
            "subreddit": source_label,
            "title": title,
            "selftext": summary[:2000],
            "url": link,
            "score": 0,
            "num_comments": 0,
            "created_utc": _parse_date(date),
        })
    return out


async def _fetch_one(client, url: str, label: str) -> list[dict]:
    resp = await client.get(url)
    resp.raise_for_status()
    return parse_rss(resp.text, label)


async def fetch_rss_osint(feeds: list[tuple[str, str]] | None = None) -> list[dict]:
    """Fetch every configured feed → raw candidates. One bad feed must not sink the rest.

    Lazy-imports httpx so parse_rss stays importable in tests without the dep.
    Feeds come from settings.osint_rss_feeds when set (comma-separated 'url|label'
    or bare 'url'), else DEFAULT_FEEDS. Returns [] only if every feed fails.
    """
    import httpx

    feeds = feeds if feeds is not None else _configured_feeds()
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                 headers={"User-Agent": USER_AGENT,
                                          "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"}) as client:
        results = await asyncio.gather(
            *(_fetch_one(client, url, label) for url, label in feeds),
            return_exceptions=True,
        )
    for (url, _label), res in zip(feeds, results):
        if isinstance(res, Exception):
            logger.warning("RSS OSINT fetch failed for %s: %s", url, res)
            continue
        out.extend(res)
    return out


def _configured_feeds() -> list[tuple[str, str]]:
    """Parse settings.osint_rss_feeds ('url|label,url|label') → list, else defaults."""
    from backend.config import get_settings

    raw = (get_settings().osint_rss_feeds or "").strip()
    if not raw:
        return DEFAULT_FEEDS
    feeds: list[tuple[str, str]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "|" in part:
            url, label = part.split("|", 1)
            feeds.append((url.strip(), label.strip()))
        else:
            feeds.append((part, "rss"))
    return feeds or DEFAULT_FEEDS
