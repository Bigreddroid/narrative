"""
Playwright scraper — fallback only. Never used for RSS sources.
Only invoked when scrape_method = 'playwright' on a source.
Requires: playwright install chromium --with-deps
"""

import hashlib
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _make_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


async def scrape_with_playwright(url: str, source_name: str) -> list[dict]:
    """
    Scrape a page using a headless Chromium browser.
    Returns list of article dicts.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: playwright install chromium --with-deps")
        return []

    articles = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(2000)

            # Extract article links
            links = await page.evaluate("""
                () => {
                    const anchors = [...document.querySelectorAll('a[href]')];
                    return anchors
                        .map(a => ({ href: a.href, text: a.innerText?.trim() }))
                        .filter(a => a.text && a.text.length > 30 && a.href.startsWith('http'));
                }
            """)

            seen = set()
            for link in links[:50]:
                href = link.get("href", "")
                text = link.get("text", "")
                if href in seen:
                    continue
                seen.add(href)

                # Try to get article content
                content = ""
                try:
                    article_page = await context.new_page()
                    await article_page.goto(href, wait_until="domcontentloaded", timeout=20_000)
                    content = await article_page.evaluate("""
                        () => {
                            const article = document.querySelector('article, main, [role="main"]');
                            return article ? article.innerText?.slice(0, 3000) : '';
                        }
                    """)
                    await article_page.close()
                except Exception:
                    pass

                articles.append({
                    "title": text,
                    "url": href,
                    "url_hash": _make_url_hash(href),
                    "content": content,
                    "published_at": None,
                })

            await browser.close()

    except Exception as exc:
        logger.error("Playwright scrape failed for %s: %s", source_name, exc)

    logger.info("Playwright scraped %d articles from %s", len(articles), source_name)
    return articles
