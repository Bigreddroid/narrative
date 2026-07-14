import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.article import Article
from backend.models.source import Source
from backend.scrapers.bs4_scraper import scrape_page_links
from backend.scrapers.playwright_scraper import scrape_with_playwright
from backend.scrapers.rss_parser import fetch_rss

logger = logging.getLogger(__name__)


async def scrape_source(source: Source, db: AsyncSession) -> tuple[int, int]:
    """Returns (scraped_count, new_count)."""
    if source.scrape_method == "rss" and source.rss_url:
        raw_articles = await fetch_rss(source.rss_url, source.name)
    elif source.scrape_method == "bs4":
        raw_articles = await scrape_page_links(source.url)
    elif source.scrape_method == "playwright":
        raw_articles = await scrape_with_playwright(source.url, source.name)
    else:
        logger.warning("No valid scrape method for source %s", source.name)
        return 0, 0

    if not raw_articles:
        return 0, 0

    hashes = [a["url_hash"] for a in raw_articles]
    existing = await db.execute(
        select(Article.url_hash).where(Article.url_hash.in_(hashes))
    )
    existing_hashes = {row[0] for row in existing}

    new_rows = [
        {
            "id": uuid.uuid4(),
            "source_id": source.id,
            "title": data["title"],
            "url": data["url"],
            "url_hash": data["url_hash"],
            "content": data.get("content", ""),
            "published_at": data.get("published_at"),
        }
        for data in raw_articles
        if data["url_hash"] not in existing_hashes
    ]

    new_count = 0
    if new_rows:
        result = await db.execute(
            pg_insert(Article).values(new_rows).on_conflict_do_nothing(index_elements=["url_hash"])
        )
        new_count = result.rowcount

    source.last_scraped_at = datetime.now(timezone.utc)
    source.scrape_error_count = 0
    db.add(source)

    logger.info(
        "Source %s: scraped=%d new=%d",
        source.name,
        len(raw_articles),
        new_count,
    )
    return len(raw_articles), new_count


async def seed_sources(db: AsyncSession) -> None:
    from backend.scrapers.sources import LAUNCH_SOURCES

    for data in LAUNCH_SOURCES:
        exists = await db.execute(select(Source).where(Source.url == data["url"]))
        # .first() (not scalar_one_or_none) so a pre-existing duplicate-URL row can
        # never raise MultipleResultsFound and abort the whole seed loop — a real
        # bug that silently stopped new sources from ever seeding once a dup existed.
        if exists.scalars().first() is not None:
            continue
        source = Source(id=uuid.uuid4(), **data)
        db.add(source)

    await db.flush()
    logger.info("Sources seeded")
