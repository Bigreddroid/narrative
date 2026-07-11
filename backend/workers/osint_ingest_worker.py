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
from backend.feeds import gdelt_osint, osint_threatintel, rss_osint
from backend.models.osint_triage_decision import OsintTriageDecision
from backend.services import cost_guard, osint_agent, runtime_config
from backend.workers.hazard_ingest_worker import _upsert

logger = logging.getLogger(__name__)


async def _log_decisions(decisions: list[dict]) -> None:
    """Persist triage decisions (the flywheel) in their OWN session, so a logging
    failure can never roll back the events already committed by the run. Best-effort:
    decision telemetry is valuable but must never block ingest."""
    if not decisions:
        return
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([OsintTriageDecision(**d) for d in decisions])
            await db.commit()
    except Exception as exc:  # noqa: BLE001 — telemetry only; never sink the run
        logger.warning("OSINT decision logging failed (%d rows): %s", len(decisions), exc)


def _osint_source():
    """(fetch_fn, source_tag) for the OSINT news source — keyless GDELT DOC API."""
    return gdelt_osint.fetch_gdelt_osint, gdelt_osint.SOURCE


async def _safe_fetch(coro, source: str) -> list[dict]:
    """Await a feed fetch, downgrading ANY failure to an empty batch. Enforces the
    'no single source can starve ingest' contract at the one place all feeds funnel
    through, so a rate-limited or down source skips its cycle instead of crashing the
    whole worker (which is what took osint_ingest down on a GDELT 429)."""
    try:
        return await coro
    except Exception as exc:  # noqa: BLE001 — one bad feed must never sink the run
        logger.warning("OSINT feed '%s' fetch failed — skipping this cycle: %s", source, exc)
        return []


async def run_osint_ingest_worker() -> dict:
    start = time.perf_counter()
    # Pick up any live admin overrides (osint_source / osint_rss_enabled) before we
    # select sources. Best-effort: if the override table is unreachable we run on the
    # env defaults, exactly as before this layer existed.
    try:
        async with AsyncSessionLocal() as db:
            await runtime_config.load(db)
    except Exception as exc:  # noqa: BLE001 — overrides are optional; env is the fallback
        logger.debug("runtime_config load skipped: %s", exc)
    fetch, source = _osint_source()
    # Source batches: the configured news source (GDELT/Reddit) + the additive,
    # keyless cyber threat-intel feed + the OSINT v2 multi-source RSS/Atom portfolio.
    # Each batch is triaged under its own source tag so events badge correctly. A
    # failing feed returns [] (best-effort, no-op) — no single source can starve ingest.
    batches = [
        (await _safe_fetch(fetch(), source), source),
        (await _safe_fetch(osint_threatintel.fetch_threatintel(), osint_threatintel.SOURCE),
         osint_threatintel.SOURCE),
    ]
    if runtime_config.osint_rss_enabled():
        batches.append((await _safe_fetch(rss_osint.fetch_rss_osint(), rss_osint.SOURCE),
                        rss_osint.SOURCE))
    total_posts = created = ingested = 0
    decisions: list[dict] = []  # one record per judged post — the triage flywheel
    async with AsyncSessionLocal() as db:
        # One budget check per run: respects the paid hard cap AND that Ollama is up.
        allow_llm = await cost_guard.llm_allowed(db)
        for posts, src in batches:
            total_posts += len(posts)
            for post in posts:
                try:
                    # triage is synchronous (LLM + geocode HTTP) — offload off the loop.
                    # triage_with_decision returns (signal, decision): the decision is
                    # logged whether the post is kept or dropped, so the rejection funnel
                    # becomes learnable data instead of vanishing.
                    signal, decision = await asyncio.to_thread(
                        osint_agent.triage_with_decision, post, allow_llm, src)
                except Exception as exc:  # noqa: BLE001 — one bad post must not sink the run
                    logger.warning("OSINT triage failed (%s): %s", post.get("external_id"), exc)
                    continue
                decisions.append(decision)
                if not signal:
                    continue
                ingested += 1
                try:
                    if await _upsert(signal, db, require_geo=False):
                        created += 1
                except Exception as exc:  # noqa: BLE001
                    logger.error("OSINT upsert failed: %s", exc)

        await db.commit()
    # Decisions persist in their own session AFTER events commit, so telemetry can't
    # roll back ingest.
    await _log_decisions(decisions)
    logger.info("OSINT ingest [%s + threatintel]: %d posts, %d triaged-in, %d new, %d logged (llm=%s, %.1fs)",
                source, total_posts, ingested, created, len(decisions), allow_llm, time.perf_counter() - start)
    return {"posts": total_posts, "ingested": ingested, "created": created,
            "llm": allow_llm, "source": source, "logged": len(decisions)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_osint_ingest_worker())
