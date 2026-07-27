import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.article import Article
from backend.models.source import Source
from backend.scrapers.bs4_scraper import scrape_page_links
from backend.scrapers.playwright_scraper import scrape_with_playwright
from backend.scrapers.rss_parser import fetch_rss

logger = logging.getLogger(__name__)


def is_scrapeable(source: Source) -> bool:
    """True when this row actually names something we can fetch.

    Not every `sources` row is a feed. hazard_ingest_worker creates one per distinct
    PUBLISHER name so corroboration can count outlets rather than feed labels, and
    those carry url="" with no rss_url. Because `is_active` defaults to True and
    `scrape_method` defaults to "rss", every one of them was landing in the scrape
    worker's work list, falling through the method dispatch, and returning early —
    570 of 688 active sources looked permanently un-attempted, and each run logged
    570 warnings about it. They are not broken feeds; they are not feeds.
    """
    method = (source.scrape_method or "").strip()
    if method == "rss":
        return bool((source.rss_url or "").strip())
    if method in ("bs4", "playwright"):
        return bool((source.url or "").strip())
    return False


def scrapeable_clause():
    """The SQL half of is_scrapeable, so the worker never fetches the rows either.

    Deliberately duplicated in two forms: the query keeps unscrapeable rows out of
    the work list, and the predicate above stops anything that slips through being
    stamped as a healthy check.
    """
    return or_(
        and_(Source.scrape_method == "rss",
             Source.rss_url.isnot(None), func.btrim(Source.rss_url) != ""),
        and_(Source.scrape_method.in_(("bs4", "playwright")),
             Source.url.isnot(None), func.btrim(Source.url) != ""),
    )


async def scrape_source(source: Source, db: AsyncSession) -> tuple[int, int]:
    """Returns (scraped_count, new_count)."""
    if not is_scrapeable(source):
        # Not an error and not a success — there is nothing here to fetch, so it must
        # NOT be stamped with last_scraped_at as though we had checked it.
        logger.debug("Source %s has no fetchable target for method %r",
                     source.name, source.scrape_method)
        return 0, 0

    if source.scrape_method == "rss":
        raw_articles = await fetch_rss(source.rss_url, source.name)
    elif source.scrape_method == "bs4":
        raw_articles = await scrape_page_links(source.url)
    else:
        raw_articles = await scrape_with_playwright(source.url, source.name)

    now = datetime.now(timezone.utc)

    # None means the source could not be READ. [] means it answered with nothing.
    # Both are attempts and both are recorded; only the first is a failure. Returning
    # early on `not raw_articles` conflated them, so a dead feed never incremented an
    # error AND never recorded an attempt — invisible in both directions.
    if raw_articles is None:
        source.scrape_error_count = (source.scrape_error_count or 0) + 1
        source.last_scraped_at = now
        db.add(source)
        logger.warning("Source %s failed to fetch (consecutive failures: %d)",
                       source.name, source.scrape_error_count)
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

    source.last_scraped_at = now
    source.scrape_error_count = 0    # a successful read clears the failure streak
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
