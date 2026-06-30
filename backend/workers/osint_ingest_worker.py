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

from backend.config import get_settings
from backend.database import AsyncSessionLocal
from backend.feeds import gdelt_osint, osint_disinfo, osint_threatintel, reddit_osint, rss_osint
from backend.services import cost_guard, osint_agent
from backend.workers.hazard_ingest_worker import _upsert

logger = logging.getLogger(__name__)


def _osint_source():
    """(fetch_fn, source_tag) for the configured OSINT source. Default = keyless GDELT;
    Reddit stays available behind OSINT_SOURCE=reddit (uses OAuth when creds are set)."""
    if (get_settings().osint_source or "gdelt").lower() == "reddit":
        return reddit_osint.fetch_reddit_osint, reddit_osint.SOURCE
    return gdelt_osint.fetch_gdelt_osint, gdelt_osint.SOURCE


async def run_osint_ingest_worker() -> dict:
    start = time.perf_counter()
    fetch, source = _osint_source()
    # Source batches: the configured news source (GDELT/Reddit) + the additive,
    # keyless cyber threat-intel feed + the OSINT v2 multi-source RSS/Atom portfolio.
    # Each batch is triaged under its own source tag so events badge correctly. A
    # failing feed returns [] (best-effort, no-op) — no single source can starve ingest.
    batches = [
        (await fetch(), source),
        (await osint_threatintel.fetch_threatintel(), osint_threatintel.SOURCE),
    ]
    if (get_settings().osint_rss_enabled):
        batches.append((await rss_osint.fetch_rss_osint(), rss_osint.SOURCE))
    total_posts = created = ingested = 0
    async with AsyncSessionLocal() as db:
        # One budget check per run: respects the paid hard cap AND that Ollama is up.
        allow_llm = await cost_guard.llm_allowed(db)
        for posts, src in batches:
            total_posts += len(posts)
            for post in posts:
                try:
                    # triage is synchronous (LLM + geocode HTTP) — offload off the loop.
                    signal = await asyncio.to_thread(osint_agent.triage, post, allow_llm, src)
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

        # Curated disinfo feed: editorial fact-check sources are pre-vetted, so they
        # skip relevance triage and upsert directly as 'disinfo' Signals.
        disinfo_signals = await osint_disinfo.fetch_disinfo()
        total_posts += len(disinfo_signals)
        for signal in disinfo_signals:
            ingested += 1
            try:
                if await _upsert(signal, db, require_geo=False):
                    created += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("OSINT disinfo upsert failed: %s", exc)
        await db.commit()
    logger.info("OSINT ingest [%s + threatintel + disinfo]: %d posts, %d triaged-in, %d new (llm=%s, %.1fs)",
                source, total_posts, ingested, created, allow_llm, time.perf_counter() - start)
    return {"posts": total_posts, "ingested": ingested, "created": created,
            "llm": allow_llm, "source": source}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_osint_ingest_worker())
