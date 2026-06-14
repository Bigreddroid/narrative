import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TheNarrative/1.0; "
        "+https://thenarrative.io/bot)"
    )
}


def _make_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _parse_date(entry: Any) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def _extract_content(entry: Any) -> str:
    if hasattr(entry, "content") and entry.content:
        return entry.content[0].get("value", "")
    if hasattr(entry, "summary"):
        return entry.summary or ""
    return ""


async def fetch_rss(rss_url: str, source_name: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(rss_url)
            resp.raise_for_status()
            raw = resp.text
    except Exception as exc:
        logger.warning("RSS fetch failed for %s (%s): %s", source_name, rss_url, exc)
        return []

    feed = feedparser.parse(raw)
    articles = []

    for entry in feed.entries:
        url = getattr(entry, "link", None)
        title = getattr(entry, "title", None)

        if not url or not title:
            continue

        articles.append(
            {
                "title": title.strip(),
                "url": url.strip(),
                "url_hash": _make_url_hash(url.strip()),
                "content": _extract_content(entry),
                "published_at": _parse_date(entry),
            }
        )

    logger.info("Parsed %d articles from %s", len(articles), source_name)
    return articles
