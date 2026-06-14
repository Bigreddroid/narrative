"""
SIMPLIFIED for customer-centric Bloomberg terminal vision (lean news/data + impact, not over-engineered consequence pipeline).
Basic clustering for grouping news into events/topics.
For enterprise end: can restore full complexity later.
Kept for compatibility with current DB/models during remodel.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.article import Article
from backend.models.narrative_event import NarrativeEvent

logger = logging.getLogger(__name__)
settings = get_settings()


async def cluster_article(article: Article, db: AsyncSession) -> NarrativeEvent | None:
    """
    Find the most similar existing NarrativeEvent for this article.
    If similarity >= threshold, assign article to that event.
    Otherwise, create a new NarrativeEvent from this article.
    Returns the NarrativeEvent (existing or new).
    """
    if article.embedding is None:
        logger.debug("Article %s has no embedding, skipping cluster", article.id)
        return None

    embedding_str = f"[{','.join(str(v) for v in article.embedding)}]"
    threshold = settings.cluster_similarity_threshold

    # Find closest event by cosine similarity
    result = await db.execute(
        text("""
            SELECT id, canonical_title,
                   1 - (embedding <=> CAST(:embedding AS vector(1024))) AS similarity
            FROM narrative_events
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector(1024))
            LIMIT 1
        """),
        {"embedding": embedding_str},
    )
    row = result.fetchone()

    if row and row.similarity >= threshold:
        event = await db.get(NarrativeEvent, row.id)
        if event:
            article.narrative_event_id = event.id
            article.is_clustered = True
            db.add(article)
            logger.debug(
                "Article '%s' clustered into event '%s' (sim=%.3f)",
                article.title[:60],
                event.canonical_title[:60],
                row.similarity,
            )
            return event

    # No close match — create new event from this article
    event = NarrativeEvent(
        id=uuid.uuid4(),
        canonical_title=article.title,
        canonical_summary=None,
        embedding=article.embedding,
        first_detected_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()

    article.narrative_event_id = event.id
    article.is_clustered = True
    db.add(article)

    logger.info("New event created: '%s'", event.canonical_title[:80])
    return event


async def cluster_unprocessed_articles(db: AsyncSession) -> tuple[int, int]:
    """
    Cluster all embedded-but-unclustered articles.
    Returns (articles_processed, new_events_created).
    """
    result = await db.execute(
        select(Article)
        .where(Article.is_embedded == True)
        .where(Article.is_clustered == False)
        .order_by(Article.scraped_at.asc())
        .limit(500)
    )
    articles = result.scalars().all()

    if not articles:
        return 0, 0

    existing_result = await db.execute(select(NarrativeEvent.id))
    seen_ids = {row[0] for row in existing_result.all()}

    new_events = 0
    for article in articles:
        event = await cluster_article(article, db)
        if event and event.id not in seen_ids:
            new_events += 1
            seen_ids.add(event.id)

    await db.flush()
    return len(articles), new_events
