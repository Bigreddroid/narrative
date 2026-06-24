"""
Pipeline scheduler — runs all 11 workers on their defined intervals.
Runs as a separate process alongside the API.
Uses asyncio for lightweight scheduling (no external job queue needed for MVP).
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_shutdown = False


def _handle_shutdown(sig, frame):
    global _shutdown
    logger.info("Shutdown signal received (%s)", sig)
    _shutdown = True


signal.signal(signal.SIGINT, _handle_shutdown)
signal.signal(signal.SIGTERM, _handle_shutdown)


async def _run_with_interval(name: str, coro_factory, interval_seconds: int):
    while not _shutdown:
        try:
            logger.info("Worker start: %s", name)
            await coro_factory()
            logger.info("Worker done: %s", name)
        except Exception as exc:
            logger.error("Worker %s crashed: %s", name, exc, exc_info=True)

        if _shutdown:
            break
        await asyncio.sleep(interval_seconds)


async def main():
    from backend.config import get_settings
    s = get_settings()

    from backend.workers.scrape_worker import run_scrape_worker
    from backend.workers.embed_worker import run_embed_worker
    from backend.workers.cluster_worker import run_cluster_worker
    from backend.workers.importance_worker import run_importance_worker
    from backend.workers.mapping_worker import run_mapping_worker
    from backend.workers.graph_worker import run_graph_worker
    from backend.workers.evolution_worker import run_evolution_worker
    from backend.workers.feed_worker import run_feed_worker
    from backend.workers.alert_worker import run_alert_worker
    from backend.workers.outcome_worker import run_outcome_worker
    from backend.workers.archive_worker import run_archive_worker
    from backend.workers.exposure_snapshot_worker import run_exposure_snapshot_worker
    from backend.workers.hazard_ingest_worker import run_hazard_ingest_worker
    from backend.workers.market_ingest_worker import run_market_ingest_worker
    from backend.workers.osint_ingest_worker import run_osint_ingest_worker

    tasks = [
        asyncio.create_task(
            _run_with_interval("scrape_worker", run_scrape_worker, s.scrape_interval_hours * 3600)
        ),
        asyncio.create_task(
            _run_with_interval("embed_worker", run_embed_worker, s.embed_interval_minutes * 60)
        ),
        asyncio.create_task(
            _run_with_interval("cluster_worker", run_cluster_worker, s.cluster_interval_minutes * 60)
        ),
        asyncio.create_task(
            _run_with_interval("importance_worker", run_importance_worker, s.importance_interval_minutes * 60)
        ),
        asyncio.create_task(
            _run_with_interval("mapping_worker", run_mapping_worker, s.mapping_interval_minutes * 60)
        ),
        asyncio.create_task(
            _run_with_interval("graph_worker", run_graph_worker, s.graph_interval_hours * 3600)
        ),
        asyncio.create_task(
            _run_with_interval("evolution_worker", run_evolution_worker, s.evolution_interval_hours * 3600)
        ),
        asyncio.create_task(
            _run_with_interval("feed_worker", run_feed_worker, s.feed_rebuild_interval_hours * 3600)
        ),
        asyncio.create_task(
            _run_with_interval("alert_worker", run_alert_worker, s.alert_interval_minutes * 60)
        ),
        asyncio.create_task(
            _run_with_interval("outcome_worker", run_outcome_worker, s.outcome_eval_interval_days * 86400)
        ),
        asyncio.create_task(
            _run_with_interval("archive_worker", run_archive_worker, s.archive_interval_hours * 3600)
        ),
        asyncio.create_task(
            _run_with_interval("exposure_snapshot_worker", run_exposure_snapshot_worker, s.exposure_snapshot_interval_hours * 3600)
        ),
        asyncio.create_task(
            _run_with_interval("hazard_ingest_worker", run_hazard_ingest_worker, s.hazard_ingest_interval_minutes * 60)
        ),
        asyncio.create_task(
            _run_with_interval("market_ingest_worker", run_market_ingest_worker, s.market_ingest_interval_minutes * 60)
        ),
        asyncio.create_task(
            _run_with_interval("osint_ingest_worker", run_osint_ingest_worker, s.osint_ingest_interval_minutes * 60)
        ),
    ]

    logger.info("Pipeline scheduler started with %d workers", len(tasks))

    while not _shutdown:
        await asyncio.sleep(1)

    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Scheduler shut down cleanly")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main())
