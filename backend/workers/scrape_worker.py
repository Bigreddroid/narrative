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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import AsyncSessionLocal
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.source import Source
from backend.scrapers.engine import scrape_source, seed_sources

logger = logging.getLogger(__name__)


async def run_scrape_worker() -> dict:
    start = time.perf_counter()
    total_scraped = 0
    total_new = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        await seed_sources(db)
        await db.commit()

        sources_result = await db.execute(
            select(Source).where(Source.is_active == True)
        )
        sources = sources_result.scalars().all()

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
        "Scrape worker done: scraped=%d new=%d errors=%d duration=%.1fs",
        total_scraped,
        total_new,
        errors,
        duration,
    )
    return {"scraped": total_scraped, "new": total_new, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scrape_worker())
