"""
pgvector cosine-similarity clustering — groups articles into narrative_events.
No AI. Pure vector math + the decision logic in cluster_logic.py.

Candidates are restricted to a recent time window and their similarity is
time-decayed; a hysteresis pair of thresholds decides attach-vs-spawn; and each
event's embedding is maintained as the running mean of its members.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.consequence_engine import cluster_logic
from backend.models.article import Article
from backend.models.narrative_event import NarrativeEvent

logger = logging.getLogger(__name__)
settings = get_settings()

CANDIDATE_LIMIT = 5


def _hours_between(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    return abs((a - b).total_seconds()) / 3600.0


async def cluster_article(article: Article, db: AsyncSession) -> NarrativeEvent | None:
    """Attach the article to its best recent event, or spawn a new one."""
    if article.embedding is None:
        logger.debug("Article %s has no embedding, skipping cluster", article.id)
        return None

    embedding_str = f"[{','.join(str(v) for v in article.embedding)}]"
    window_start = datetime.now(timezone.utc) - timedelta(days=settings.cluster_time_window_days)

    candidate_rows = (await db.execute(
        text("""
            SELECT id, first_detected_at, last_updated_at,
                   1 - (embedding <=> CAST(:embedding AS vector(1024))) AS similarity
            FROM narrative_events
            WHERE embedding IS NOT NULL
              AND first_detected_at >= :window_start
            ORDER BY embedding <=> CAST(:embedding AS vector(1024))
            LIMIT :limit
        """),
        {"embedding": embedding_str, "window_start": window_start, "limit": CANDIDATE_LIMIT},
    )).fetchall()

    chosen_id = None
    member_count = 0
    if candidate_rows:
        counts = dict((await db.execute(
            select(Article.narrative_event_id, func.count())
            .where(Article.narrative_event_id.in_([r.id for r in candidate_rows]))
            .group_by(Article.narrative_event_id)
        )).all())

        article_ts = article.published_at or article.scraped_at
        candidates = [
            {
                "id": r.id,
                "sim": float(r.similarity),
                "age_gap_hours": _hours_between(article_ts, r.last_updated_at or r.first_detected_at),
                "member_count": counts.get(r.id, 0),
            }
            for r in candidate_rows
        ]
        chosen_id, _ = cluster_logic.decide_cluster(
            candidates,
            settings.cluster_attach_threshold,
            settings.cluster_strong_threshold,
            settings.cluster_min_established,
            settings.cluster_time_decay_days * 24,
        )
        member_count = next((c["member_count"] for c in candidates if c["id"] == chosen_id), 0)

    if chosen_id is not None:
        event = await db.get(NarrativeEvent, chosen_id)
        if event:
            event.embedding = cluster_logic.update_centroid(event.embedding, article.embedding, member_count)
            event.last_updated_at = datetime.now(timezone.utc)
            db.add(event)
            article.narrative_event_id = event.id
            article.is_clustered = True
            db.add(article)
            logger.debug("Article '%s' clustered into event '%s'", article.title[:60], event.canonical_title[:60])
            return event

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
        .where(Article.is_embedded == True)  # noqa: E712
        .where(Article.is_clustered == False)  # noqa: E712
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
