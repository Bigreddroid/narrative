"""
Article embeddings.

Local & free by default (fastembed / BAAI/bge-large-en-v1.5), with Voyage AI as
an opt-in paid provider. Both emit 1024-dim vectors, so either matches the
pgvector schema (Vector(1024)) with no migration. Never use Claude for embeddings.

Provider selection (backend/config.py):
  - embeddings_provider = "local"  → fastembed, $0 (default)
  - embeddings_provider = "voyage" → paid; honoured only when paid_apis_enabled=True.
"""

import logging
from functools import lru_cache

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BATCH_SIZE = 50
EMBED_DIM = 1024


def _provider() -> str:
    """Paid 'voyage' downgrades to local when the master switch is off."""
    p = settings.embeddings_provider
    if p == "voyage" and not settings.paid_apis_enabled:
        return "local"
    return p


@lru_cache(maxsize=1)
def _local_model():
    from fastembed import TextEmbedding

    logger.info("Loading local embedding model: %s", settings.local_embedding_model)
    # When a cache dir is configured (e.g. a Railway volume at /data/models), the
    # model is downloaded once and reused across restarts instead of being re-fetched
    # into the ephemeral container FS every boot. Empty ⇒ library default.
    kwargs: dict = {}
    if settings.fastembed_cache_dir:
        kwargs["cache_dir"] = settings.fastembed_cache_dir
    return TextEmbedding(model_name=settings.local_embedding_model, **kwargs)


def _embed_local(texts: list[str]) -> list[list[float]]:
    # fastembed batches internally and runs on ONNX (no torch); returns np arrays.
    model = _local_model()
    return [[float(x) for x in vec] for vec in model.embed(texts)]


def _embed_voyage(texts: list[str]) -> list[list[float]]:
    import voyageai

    client = voyageai.Client(api_key=settings.voyage_api_key)
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        result = client.embed(batch, model=settings.embedding_model, input_type="document")
        out.extend(result.embeddings)
        logger.debug("Voyage embedded batch %d-%d", i, i + len(batch))
    return out


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts. Input is title + first 1000 chars of content.
    Returns a list of 1024-dim float vectors. On hard failure, returns zero
    vectors (last-resort fallback) so the pipeline keeps flowing.
    """
    if not texts:
        return []

    provider = _provider()
    try:
        if provider == "voyage":
            return _embed_voyage(texts)
        return _embed_local(texts)
    except Exception as exc:
        logger.error("Embedding failed (provider=%s): %s — using zero vectors", provider, exc)
        return [[0.0] * EMBED_DIM for _ in texts]


def make_article_text(title: str, content: str | None) -> str:
    """Combine title and content for embedding input."""
    content_preview = (content or "")[:1000]
    return f"{title}\n\n{content_preview}".strip()
