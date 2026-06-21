"""
STEP 11 — ARCHIVE (every 24 hours)
Articles > 30 days → compress (mark is_archived).
Embeddings > 6 months → R2.
Consequence maps > 6 months → R2.
narrative_events, event_connections, event_revisions,
prediction_outcomes kept hot forever (the moat dataset).
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta

import boto3
from botocore.client import Config
from sqlalchemy import select, text

from backend.config import get_settings
from backend.database import AsyncSessionLocal
from backend.models.article import Article
from backend.models.pipeline_metrics import PipelineMetric

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.cloudflare_r2_endpoint,
        aws_access_key_id=settings.cloudflare_r2_access_key,
        aws_secret_access_key=settings.cloudflare_r2_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


async def archive_old_articles(db) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.hot_data_days)
    result = await db.execute(
        text("""
            UPDATE articles
            SET is_archived = TRUE, content = NULL, embedding = NULL
            WHERE scraped_at < :cutoff
              AND is_archived = FALSE
            RETURNING id
        """),
        {"cutoff": cutoff},
    )
    archived_ids = result.fetchall()
    logger.info("Archived %d old articles (content + embedding cleared)", len(archived_ids))
    return len(archived_ids)


async def upload_old_maps_to_r2(db) -> int:
    if not settings.cloudflare_r2_endpoint:
        logger.debug("R2 not configured, skipping cold archive upload")
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.warm_data_months * 30)

    result = await db.execute(
        text("""
            SELECT ecm.id, ecm.narrative_event_id, ecm.consequence_chain,
                   ecm.direct_impact, ecm.indirect_impact, ecm.created_at
            FROM event_consequence_maps ecm
            WHERE ecm.created_at < :cutoff
              AND ecm.is_suppressed = FALSE
            LIMIT 100
        """),
        {"cutoff": cutoff},
    )
    rows = result.fetchall()

    if not rows:
        return 0

    try:
        r2 = _get_r2_client()
    except Exception as exc:
        logger.warning("R2 client init failed: %s", exc)
        return 0

    uploaded = 0
    for row in rows:
        map_id, event_id, chain, direct, indirect, created_at = row
        key = f"consequence_maps/{event_id}/{map_id}.json"
        payload = json.dumps(
            {
                "id": str(map_id),
                "narrative_event_id": str(event_id),
                "consequence_chain": chain,
                "direct_impact": direct,
                "indirect_impact": indirect,
                "archived_at": created_at.isoformat() if created_at else None,
            },
            default=str,
        )
        try:
            r2.put_object(
                Bucket=settings.cloudflare_r2_bucket,
                Key=key,
                Body=payload.encode(),
                ContentType="application/json",
            )
            uploaded += 1
        except Exception as exc:
            logger.warning("R2 upload failed for map %s: %s", map_id, exc)

    logger.info("Uploaded %d consequence maps to R2 cold storage", uploaded)
    return uploaded


async def run_archive_worker() -> dict:
    start = time.perf_counter()
    archived = 0
    r2_uploads = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        try:
            archived = await archive_old_articles(db)
            await db.commit()
        except Exception as exc:
            logger.error("Article archive failed: %s", exc)
            errors += 1

        try:
            r2_uploads = await upload_old_maps_to_r2(db)
        except Exception as exc:
            logger.error("R2 upload failed: %s", exc)
            errors += 1

        duration = time.perf_counter() - start
        metric = PipelineMetric(
            id=uuid.uuid4(),
            worker_name="archive_worker",
            errors=errors,
            duration_seconds=round(duration, 2),
        )
        db.add(metric)
        await db.commit()

    logger.info(
        "Archive worker done: archived=%d r2_uploads=%d errors=%d duration=%.1fs",
        archived,
        r2_uploads,
        errors,
        time.perf_counter() - start,
    )
    return {"archived": archived, "r2_uploads": r2_uploads, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_archive_worker())
