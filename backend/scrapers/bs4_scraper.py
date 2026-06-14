import hashlib
import logging
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _make_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _extract_article_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()

    candidates = soup.select("article, main, [role='main'], .article-body, .post-content")
    if candidates:
        return " ".join(candidates[0].get_text(separator=" ", strip=True).split())

    body = soup.find("body")
    if body:
        return " ".join(body.get_text(separator=" ", strip=True).split())

    return ""


async def scrape_article_content(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=20, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            return _extract_article_text(soup)
    except Exception as exc:
        logger.debug("BS4 scrape failed for %s: %s", url, exc)
        return ""


async def scrape_page_links(base_url: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=20, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(base_url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        logger.warning("BS4 page scrape failed for %s: %s", base_url, exc)
        return []

    articles = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("http"):
            continue
        if href in seen:
            continue
        seen.add(href)

        title = a.get_text(strip=True)
        if len(title) < 20:
            continue

        articles.append(
            {
                "title": title,
                "url": href,
                "url_hash": _make_url_hash(href),
                "content": "",
                "published_at": None,
            }
        )

    return articles
