"""
One-off: embed the mapped-event backlog + rebuild event_connections from scratch
with semantic-gated, IDF-weighted edges (populating weight_breakdown.cosine).

Why: the existing connection graph is tag-only — the semantic gate (SEMANTIC_FLOOR)
was added after the current ~282k edges were built, and ~⅔ of mapped events carry
no embedding, so their edges are generic-tag coincidences with no cosine/geo signal.
The consequence tracer (graph.py /event/{id}/trace) can only surface *grounded*
causal chains once edges carry that signal. This backfills embeddings on every
mapped event (embedding its own canonical_title+summary, same 1024-dim space as the
query-time embedder) then rebuilds all edges.

Runs against whatever DATABASE_URL is configured (local or prod). Full rebuild:
TRUNCATE event_connections, then recompute the upper triangle. The O(n²) cosine is
done once as a numpy matrix and injected into graph_connector.compute_connection_weight,
so the run is minutes, not hours.

Usage (from repo root):
    python -m scripts.recompute_connections            # uses .env DATABASE_URL (local)
    DATABASE_URL=postgresql+asyncpg://…prod… python -m scripts.recompute_connections
"""

import asyncio
import time
import uuid

import numpy as np
from sqlalchemy import delete, select

from backend.consequence_engine import graph_connector
from backend.consequence_engine.embedder import embed_texts
from backend.database import AsyncSessionLocal
from backend.models.event_connection import EventConnection
from backend.models.narrative_event import NarrativeEvent

EMBED_BATCH = 64
COMMIT_EVERY = 200  # source events per commit during the rebuild


async def embed_backlog(db) -> int:
    rows = (await db.execute(
        select(NarrativeEvent)
        .where(NarrativeEvent.is_mapped == True)  # noqa: E712
        .where(NarrativeEvent.embedding.is_(None))
    )).scalars().all()
    if not rows:
        print("embed backlog: nothing to embed")
        return 0
    print(f"embed backlog: {len(rows)} mapped events need embeddings")
    embedded = 0
    for i in range(0, len(rows), EMBED_BATCH):
        chunk = rows[i:i + EMBED_BATCH]
        texts = [f"{e.canonical_title or ''}. {e.canonical_summary or ''}".strip() for e in chunk]
        vecs = embed_texts(texts)
        for e, v in zip(chunk, vecs):
            if v and any(v):  # skip zero vectors (embedder hard-failure)
                e.embedding = list(v)
                embedded += 1
        await db.commit()
        print(f"  embedded {min(i + EMBED_BATCH, len(rows))}/{len(rows)}")
    return embedded


def _cosine_lookup(corpus):
    """Build (cos_row, row_of) once from a normalized embedding matrix.

    cos_row(a_i) -> vector of cosines from event a_i to every embedded event (indexed
    by matrix row via row_of), or None when a_i is unembedded."""
    row_of: dict[int, int] = {}
    mat = []
    for i, e in enumerate(corpus):
        v = e.embedding
        if v is None:
            continue
        arr = np.asarray(list(v), dtype=np.float32)
        norm = float(np.linalg.norm(arr))
        if norm > 0.0:
            row_of[i] = len(mat)
            mat.append(arr / norm)
    M = np.vstack(mat) if mat else None

    def cos_row(a_i: int):
        if M is None or a_i not in row_of:
            return None
        return M @ M[row_of[a_i]]  # cosine to every embedded event, indexed by matrix row

    return cos_row, row_of


async def rebuild_connections(db) -> int:
    corpus = (await db.execute(
        select(NarrativeEvent).where(NarrativeEvent.is_mapped == True)  # noqa: E712
    )).scalars().all()
    n = len(corpus)
    print(f"rebuild: {n} mapped events; building IDF + cosine matrix…")
    idf = graph_connector._build_idf_context(corpus)
    cos_row, row_of = _cosine_lookup(corpus)
    print(f"rebuild: {len(row_of)}/{n} events embedded; truncating event_connections…")

    await db.execute(delete(EventConnection))
    await db.commit()

    created = 0
    for a_i in range(n):
        a = corpus[a_i]
        crow = cos_row(a_i)
        batch = []
        for b_i in range(a_i + 1, n):
            cos = float(crow[row_of[b_i]]) if (crow is not None and b_i in row_of) else None
            cd = graph_connector.compute_connection_weight(a, corpus[b_i], idf, cos=cos)
            if cd:
                batch.append(EventConnection(
                    id=uuid.uuid4(), event_a_id=a.id, event_b_id=corpus[b_i].id, **cd))
        if batch:
            db.add_all(batch)
            created += len(batch)
        a.is_graph_connected = True
        if a_i % COMMIT_EVERY == 0:
            await db.commit()
            print(f"  source {a_i}/{n} — edges so far: {created}")
    await db.commit()
    return created


async def main():
    async with AsyncSessionLocal() as db:
        t0 = time.time()
        emb = await embed_backlog(db)
        print(f"== embedded {emb} events ==")
        edges = await rebuild_connections(db)
        print(f"== rebuilt {edges} connections in {time.time() - t0:.0f}s ==")


if __name__ == "__main__":
    asyncio.run(main())
