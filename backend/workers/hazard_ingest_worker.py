"""
HAZARD INGEST — pulls free real-time feeds and upserts them as real NarrativeEvents.

Replaces the LLM pipeline for free-source events: fetch → synthesize consequence
map (deterministic) → upsert by (source, external_id). No mock data, no paid keys.
Add a source by appending its fetch() to SOURCES.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.feeds import cyber, gdacs, launches, synthesize, usgs, weather
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.narrative_event import NarrativeEvent

logger = logging.getLogger(__name__)

# Geo-located sources (each returns a list of Signal dicts with lat/lng).
# NOTE: gdelt.fetch_gdelt is intentionally NOT wired — the GDELT GEO 2.0 endpoint
# returns 404 from our hosts (the DOC API works but has no per-point coords).
# The module + tests remain; re-add once a working geocoded endpoint is confirmed.
SOURCES = [usgs.fetch_earthquakes, weather.fetch_weather, gdacs.fetch_gdacs,
           launches.fetch_launches]

# Non-geo sources (lat/lng=None): ingested without coordinates. Filtered to
# high-signal items only (NONGEO_MIN_IMPORTANCE) to keep the feed clean — e.g.
# CISA KEV emits importance 80 only for ransomware-flagged vulnerabilities.
NONGEO_SOURCES = [cyber.fetch_kev]
NONGEO_MIN_IMPORTANCE = 80


async def _gather(sources: list) -> list[dict]:
    signals: list[dict] = []
    for fetch in sources:
        try:
            signals.extend(await fetch() or [])
        except Exception as exc:  # noqa: BLE001 — one bad feed must not sink the rest
            logger.warning("Feed fetch failed (%s): %s", getattr(fetch, "__name__", fetch), exc)
    return signals


async def _upsert(signal: dict, db, require_geo: bool = True) -> bool:
    """Create or refresh a NarrativeEvent from a Signal. Returns True if newly created.

    Geo sources require coordinates; non-geo sources (require_geo=False) are stored
    with null centroid (they contribute sector exposure but never plot on the map).
    """
    sid, ext = signal.get("source"), signal.get("external_id")
    if require_geo and (signal.get("lat") is None or signal.get("lng") is None):
        return False

    existing = None
    if sid and ext:
        existing = (await db.execute(
            select(NarrativeEvent).where(NarrativeEvent.source == sid).where(NarrativeEvent.external_id == ext)
        )).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing:
        existing.global_importance_score = signal["importance"]
        existing.current_status = signal["status"]
        existing.last_updated_at = now
        db.add(existing)
        return False

    syn = synthesize.synthesize(signal)
    event = NarrativeEvent(
        id=uuid.uuid4(),
        canonical_title=signal["title"],
        canonical_summary=signal.get("summary"),
        category=signal["category"],
        global_importance_score=signal["importance"],
        current_status=signal["status"],
        geographic_relevance=signal.get("geography") or [],
        affected_sectors=syn["affected_sectors"],
        geo_centroid_lat=signal.get("lat"),
        geo_centroid_lng=signal.get("lng"),
        first_detected_at=now,
        last_updated_at=now,
        is_mapped=True,
        is_importance_scored=True,
        source=sid,
        external_id=ext,
    )
    db.add(event)
    await db.flush()
    db.add(EventConsequenceMap(
        id=uuid.uuid4(),
        narrative_event_id=event.id,
        version=1,
        consensus_summary=syn["consensus_summary"],
        consequence_chain=syn["consequence_chain"],
        direct_impact=syn["direct_impact"],
        indirect_impact=syn["indirect_impact"],
        confidence=syn["confidence"],
        disputed_points=syn["disputed_points"],
        sources_analyzed=syn["sources_analyzed"],
    ))
    return True


async def run_hazard_ingest_worker() -> dict:
    start = time.perf_counter()
    geo = await _gather(SOURCES)
    nongeo = [s for s in await _gather(NONGEO_SOURCES)
              if s.get("importance", 0) >= NONGEO_MIN_IMPORTANCE]
    created = 0
    async with AsyncSessionLocal() as db:
        for s, require_geo in [(g, True) for g in geo] + [(n, False) for n in nongeo]:
            try:
                if await _upsert(s, db, require_geo=require_geo):
                    created += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("Hazard upsert failed: %s", exc)
        await db.commit()
    logger.info("Hazard ingest: %d geo + %d non-geo signals, %d new (%.1fs)",
                len(geo), len(nongeo), created, time.perf_counter() - start)
    return {"signals": len(geo) + len(nongeo), "created": created}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_hazard_ingest_worker())
