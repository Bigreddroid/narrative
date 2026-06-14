"""
LEAN pipeline scheduler.
Only core workers (scrape, embed, cluster, basic feed) run by default for terminal data.
Heavy workers (graph, importance, outcome, evolution etc.) are stretch / commented for enterprise later.
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

    # Lean core workers only for terminal (news/data + basic impact).
    # Heavy workers (importance, mapping, graph, evolution, outcome, archive) are stretch/enterprise.
    from backend.workers.scrape_worker import run_scrape_worker
    from backend.workers.embed_worker import run_embed_worker
    from backend.workers.cluster_worker import run_cluster_worker
    from backend.workers.feed_worker import run_feed_worker
    from backend.workers.alert_worker import run_alert_worker

    tasks = [
        # Lean core only for terminal MVP
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
            _run_with_interval("feed_worker", run_feed_worker, s.feed_interval_minutes * 60)
        ),
        asyncio.create_task(
            _run_with_interval("alert_worker", run_alert_worker, s.alert_interval_minutes * 60)
        ),
        # Heavy workers below are stretch for enterprise (commented in lean mode)
        # asyncio.create_task(_run_with_interval("importance_worker", ...)),
        # etc.
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
