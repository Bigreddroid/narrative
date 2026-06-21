"""
Admin worker controls — pause, resume, trigger workers.
Thin wrappers around RQ queue operations.
"""

import importlib
import logging

import redis
from rq import Queue

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

WORKER_MODULES = {
    "scrape_worker": "backend.workers.scrape_worker.run_scrape_worker",
    "embed_worker": "backend.workers.embed_worker.run_embed_worker",
    "cluster_worker": "backend.workers.cluster_worker.run_cluster_worker",
    "importance_worker": "backend.workers.importance_worker.run_importance_worker",
    "mapping_worker": "backend.workers.mapping_worker.run_mapping_worker",
    "graph_worker": "backend.workers.graph_worker.run_graph_worker",
    "evolution_worker": "backend.workers.evolution_worker.run_evolution_worker",
    "feed_worker": "backend.workers.feed_worker.run_feed_worker",
    "alert_worker": "backend.workers.alert_worker.run_alert_worker",
    "outcome_worker": "backend.workers.outcome_worker.run_outcome_worker",
    "archive_worker": "backend.workers.archive_worker.run_archive_worker",
}


def enqueue_worker(worker_name: str) -> str:
    if worker_name not in WORKER_MODULES:
        raise ValueError(f"Unknown worker: {worker_name}")

    r = redis.from_url(settings.redis_url)
    q = Queue(connection=r)

    module_path, func_name = WORKER_MODULES[worker_name].rsplit(".", 1)
    module = importlib.import_module(module_path)
    func = getattr(module, func_name)

    job = q.enqueue(func, job_timeout=600)
    logger.info("Enqueued worker %s: job_id=%s", worker_name, job.id)
    return job.id


def get_queue_depth() -> dict:
    r = redis.from_url(settings.redis_url)
    q = Queue(connection=r)
    return {
        "queued": len(q),
        "started": len(q.started_job_registry),
        "failed": len(q.failed_job_registry),
    }
