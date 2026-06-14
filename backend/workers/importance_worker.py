"""
LEAN — Basic importance scoring (stretch for advanced routing).
Kept minimal for terminal feed ordering.
"""

import asyncio
import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.consequence_engine.importance_scorer import score_article, score_cluster
from backend.database import AsyncSessionLocal
from backend.models.article import Article
from backend.models.narrative_event import NarrativeEvent
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.source import Source

logger = logging.getLogger(__name__)
settings = get_settings()


async def score_unscored_events(db: AsyncSession) -> int:
    events_result = await db.execute(
        select(NarrativeEvent)
        .where(NarrativeEvent.is_importance_scored == False)
        .where(NarrativeEvent.is_mapped == False)
        .limit(200)
    )
    events = events_result.scalars().all()

    if not events:
        return 0

    scored = 0
    for event in events:
        articles_result = await db.execute(
            select(Article, Source)
            .join(Source, Article.source_id == Source.id, isouter=True)
            .where(Article.narrative_event_id == event.id)
        )
        rows = articles_result.all()

        if not rows:
            event.is_importance_scored = True
            db.add(event)
            continue

        article_dicts = []
        for article, source in rows:
            article_score = score_article(
                article.title,
                article.content or "",
                source.name if source else "",
            )
            article.importance_score = article_score
            db.add(article)

            article_dicts.append(
                {
                    "article_score": article_score,
                    "source_name": source.name if source else "",
                }
            )

        cluster_score = score_cluster(article_dicts)
        event.global_importance_score = cluster_score
        event.is_importance_scored = True
        db.add(event)
        scored += 1

    await db.flush()
    return scored


async def run_importance_worker() -> dict:
    start = time.perf_counter()

    async with AsyncSessionLocal() as db:
        scored = await score_unscored_events(db)
        await db.commit()

        duration = time.perf_counter() - start
        metric = PipelineMetric(
            id=uuid.uuid4(),
            worker_name="importance_worker",
            events_mapped=scored,
            duration_seconds=round(duration, 2),
        )
        db.add(metric)
        await db.commit()

    logger.info(
        "Importance worker done: scored=%d duration=%.1fs",
        scored,
        time.perf_counter() - start,
    )
    return {"scored": scored}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_importance_worker())
