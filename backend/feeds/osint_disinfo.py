"""
OSINT disinformation — free, KEYLESS feed of vetted fact-check / disinformation
cases from editorial sources (PolitiFact, Snopes, Full Fact, Lead Stories).

Unlike the GDELT/Reddit OSINT sources (noisy social posts that need LLM relevance
triage), these are CURATED editorial outlets: every item is already a reviewed
disinformation case, so the worker ingests them directly as `disinfo` Signals
without triage. This covers the OSINT Framework's "Disinformation & Media
Verification" branch in the live event pipeline.

parse_disinfo() is pure + testable (no I/O); fetch_disinfo() does the HTTP + RSS
parsing. Signals carry no centroid (non-geo, like CISA KEV) — they surface in the
feed badged 'osint_disinfo' without a map marker. Source = 'osint_disinfo'.
"""

import hashlib
import logging
import time

logger = logging.getLogger(__name__)

SOURCE = "osint_disinfo"
USER_AGENT = "the-narrative-osint/0.2 (+https://thenarrative.io)"

# Keyless editorial fact-check RSS sources.
FEEDS = [
    ("PolitiFact", "https://www.politifact.com/rss/factchecks/"),
    ("Snopes", "https://www.snopes.com/feed/"),
    ("Full Fact", "https://fullfact.org/feed/all/"),
    ("Lead Stories", "https://leadstories.com/atom.xml"),
]


def _signal_from(title: str, summary: str | None, link: str, ts: float | None) -> dict:
    key = link or title
    pid = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return {
        "external_id": f"disinfo-{pid}",
        "source": SOURCE,
        "title": title.strip()[:300],
        "summary": (summary or title).strip()[:600],
        "category": "disinfo",
        # Non-geo: a fact-check rarely maps to one centroid; ingest without a marker.
        "lat": None,
        "lng": None,
        "importance": 45,
        "status": "developing",
        "geography": [],
        "ts": int(ts * 1000) if ts else None,
        "confidence": 0.5,
        "evidence_url": link or "",
    }


def parse_disinfo(entries: list | None) -> list[dict]:
    """RSS entry dicts → `disinfo` Signal dicts. Pure: no I/O.

    Each entry is a plain dict with keys: title, summary (optional), link,
    ts (epoch seconds, optional). Dedupes by link (falling back to title); skips
    entries with no title.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for e in (entries or []):
        if not isinstance(e, dict):
            continue
        title = (e.get("title") or "").strip()
        if not title:
            continue
        link = (e.get("link") or "").strip()
        key = link or title
        if key in seen:
            continue
        seen.add(key)
        out.append(_signal_from(title, e.get("summary") or e.get("description"), link, e.get("ts")))
    return out


async def fetch_disinfo(maxrecords: int = 40, per_feed: int = 12) -> list[dict]:
    """Fetch + parse the fact-check RSS feeds → `disinfo` Signals.

    Lazy-imports httpx/feedparser so parse_disinfo stays importable in tests without
    the deps. A failing feed is skipped (best-effort); never raises.
    """
    import httpx
    import feedparser

    out: list[dict] = []
    for outlet, url in FEEDS:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                         headers={"User-Agent": USER_AGENT}) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            entries = []
            for e in parsed.entries[:per_feed]:
                tp = e.get("published_parsed") or e.get("updated_parsed")
                ts = time.mktime(tp) if tp else None
                entries.append({
                    "title": e.get("title", ""),
                    "summary": e.get("summary", ""),
                    "link": e.get("link", ""),
                    "ts": ts,
                })
            out.extend(parse_disinfo(entries))
        except Exception as exc:  # noqa: BLE001 — keyless best-effort feed; never sink the run
            logger.warning("disinfo fetch failed (%s): %s", outlet, exc)
    return out[:maxrecords]
