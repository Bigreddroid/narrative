"""
OSINT INGEST — pulls open-source social signals (Reddit), runs each through the LLM
triage agent, and upserts the survivors as NarrativeEvents (source 'osint_*').

Free by default: triage uses the local LLM; when no LLM is permitted/available
(cost_guard) it degrades to a keyword heuristic. Reuses hazard_ingest_worker._upsert
for dedupe + deterministic consequence-map synthesis, so OSINT events flow through the
exact same CPE pipeline as authoritative feeds — just tagged by source so the UI can
badge them 'unverified'. require_geo=False: keep non-geolocated items (null centroid).
"""

import asyncio
import logging
import time

from backend.database import AsyncSessionLocal
from backend.feeds import reddit_osint
from backend.services import cost_guard, osint_agent
from backend.workers.hazard_ingest_worker import _upsert

logger = logging.getLogger(__name__)


async def run_osint_ingest_worker() -> dict:
    start = time.perf_counter()
    posts = await reddit_osint.fetch_reddit_osint()
    created = ingested = 0
    async with AsyncSessionLocal() as db:
        # One budget check per run: respects the paid hard cap AND that Ollama is up.
        allow_llm = await cost_guard.llm_allowed(db)
        for post in posts:
            try:
                # triage is synchronous (LLM + geocode HTTP) — offload off the loop.
                signal = await asyncio.to_thread(osint_agent.triage, post, allow_llm)
            except Exception as exc:  # noqa: BLE001 — one bad post must not sink the run
                logger.warning("OSINT triage failed (%s): %s", post.get("external_id"), exc)
                continue
            if not signal:
                continue
            ingested += 1
            try:
                if await _upsert(signal, db, require_geo=False):
                    created += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("OSINT upsert failed: %s", exc)
        await db.commit()
    logger.info("OSINT ingest: %d posts, %d triaged-in, %d new (llm=%s, %.1fs)",
                len(posts), ingested, created, allow_llm, time.perf_counter() - start)
    return {"posts": len(posts), "ingested": ingested, "created": created, "llm": allow_llm}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_osint_ingest_worker())
