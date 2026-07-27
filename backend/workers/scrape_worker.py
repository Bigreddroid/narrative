"""
STEP 1 — SCRAPE (every 2 hours)
Scrapes all active sources, deduplicates by url_hash.
Logs run to pipeline_metrics.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import AsyncSessionLocal
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.source import Source
from backend.scrapers.engine import scrape_source, scrapeable_clause, seed_sources

logger = logging.getLogger(__name__)


async def run_scrape_worker() -> dict:
    start = time.perf_counter()
    total_scraped = 0
    total_new = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        await seed_sources(db)
        await db.commit()

        # `is_active` alone is not "is a feed". hazard_ingest_worker creates a sources
        # row per PUBLISHER name so corroboration counts outlets, and those have no
        # rss_url; they were 570 of 688 active rows, every one of them fetched-then-
        # skipped on every run. Filter them out in SQL so the work list is the set we
        # can actually scrape, and the coverage numbers mean something.
        sources_result = await db.execute(
            select(Source).where(Source.is_active == True, scrapeable_clause())
        )
        sources = sources_result.scalars().all()

        skipped_result = await db.execute(
            select(func.count()).select_from(Source)
            .where(Source.is_active == True, ~scrapeable_clause())
        )
        not_feeds = skipped_result.scalar() or 0

        for source in sources:
            try:
                scraped, new = await scrape_source(source, db)
                total_scraped += scraped
                total_new += new
            except Exception as exc:
                logger.error("Scrape failed for source %s: %s", source.name, exc)
                source.scrape_error_count += 1
                db.add(source)
                errors += 1

        await db.commit()

        duration = time.perf_counter() - start
        metric = PipelineMetric(
            id=uuid.uuid4(),
            worker_name="scrape_worker",
            articles_scraped=total_new,
            errors=errors,
            duration_seconds=round(duration, 2),
        )
        db.add(metric)
        await db.commit()

    logger.info(
        "Scrape worker done: feeds=%d scraped=%d new=%d errors=%d "
        "not_feeds_skipped=%d duration=%.1fs",
        len(sources),
        total_scraped,
        total_new,
        errors,
        not_feeds,
        duration,
    )
    return {"scraped": total_scraped, "new": total_new, "errors": errors,
            "feeds": len(sources), "not_feeds_skipped": not_feeds}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scrape_worker())
