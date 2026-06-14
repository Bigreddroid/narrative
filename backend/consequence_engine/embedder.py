"""
SIMPLIFIED for customer-centric + enterprise Bloomberg terminal vision (lean news/data + impact/analytics, not over-engineered).
Voyage embeddings kept for relevance/search in terminal. For enterprise: advanced models later.
"""

import logging
from typing import Any

import voyageai

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BATCH_SIZE = 50


def _get_client() -> voyageai.Client:
    return voyageai.Client(api_key=settings.voyage_api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using Voyage AI.
    Input texts are title + first 1000 chars of content for efficiency.
    Returns list of 1024-dim float vectors.
    """
    if not texts:
        return []

    client = _get_client()
    all_embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        try:
            result = client.embed(
                batch,
                model=settings.embedding_model,
                input_type="document",
            )
            all_embeddings.extend(result.embeddings)
            logger.debug("Embedded batch %d-%d", i, i + len(batch))
        except Exception as exc:
            logger.error("Voyage embedding failed for batch %d: %s", i, exc)
            all_embeddings.extend([[0.0] * 1024] * len(batch))

    return all_embeddings


def make_article_text(title: str, content: str | None) -> str:
    """Combine title and content for embedding input."""
    content_preview = (content or "")[:1000]
    return f"{title}\n\n{content_preview}".strip()
