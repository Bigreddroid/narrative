"""
STEP 2 — EMBED (every 15 minutes)
Voyage AI voyage-large-2. Batch 50. ~$0.00012/article.
Never use Claude for embeddings.
"""

import asyncio
import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.consequence_engine.embedder import embed_texts, make_article_text
from backend.database import AsyncSessionLocal
from backend.models.article import Article
from backend.models.pipeline_metrics import PipelineMetric

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


async def run_embed_worker() -> dict:
    start = time.perf_counter()
    total_embedded = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Article)
            .where(Article.is_embedded == False)
            .where(Article.is_archived == False)
            .order_by(Article.scraped_at.asc())
            .limit(500)
        )
        articles = result.scalars().all()

        if not articles:
            logger.info("Embed worker: no articles to embed")
            return {"embedded": 0, "errors": 0}

        texts = [make_article_text(a.title, a.content) for a in articles]

        try:
            embeddings = embed_texts(texts)
        except Exception as exc:
            logger.error("Embedding batch failed: %s", exc)
            errors = len(articles)
            duration = time.perf_counter() - start
            metric = PipelineMetric(
                id=uuid.uuid4(),
                worker_name="embed_worker",
                articles_embedded=0,
                errors=errors,
                duration_seconds=round(duration, 2),
            )
            db.add(metric)
            await db.commit()
            return {"embedded": 0, "errors": errors}

        for article, embedding in zip(articles, embeddings):
            article.embedding = embedding
            article.is_embedded = True
            db.add(article)

        await db.commit()
        total_embedded = len(articles)

        duration = time.perf_counter() - start
        metric = PipelineMetric(
            id=uuid.uuid4(),
            worker_name="embed_worker",
            articles_embedded=total_embedded,
            errors=errors,
            duration_seconds=round(duration, 2),
        )
        db.add(metric)
        await db.commit()

    logger.info(
        "Embed worker done: embedded=%d errors=%d duration=%.1fs",
        total_embedded,
        errors,
        time.perf_counter() - start,
    )
    return {"embedded": total_embedded, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_embed_worker())
