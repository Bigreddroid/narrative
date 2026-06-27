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
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from backend.consequence_engine import title_dedup
from backend.database import AsyncSessionLocal
from backend.feeds import cyber, gdacs, launches, synthesize, usgs, weather
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.narrative_event import NarrativeEvent

# Only fold a new signal into an existing event detected within this window — a
# story that resurfaces weeks later is genuinely new, not a duplicate.
DEDUP_WINDOW_DAYS = 4
DEDUP_CANDIDATE_LIMIT = 200

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


async def _find_duplicate(signal: dict, db) -> NarrativeEvent | None:
    """Return a recent, same-category canonical this signal duplicates, else None.

    Two regimes, by source:
      • OSINT/news (free-text headlines that produce the "US strikes Iran" wall) —
        fuzzy title match reinforced by geography overlap.
      • Structured feeds (USGS/GDACS/NWS/launches) — only *exact* normalized-title
        matches fold (e.g. GDACS re-emitting "Earthquake in Venezuela"); their
        templated titles look similar but are distinct events, so fuzzy matching is
        unsafe here.
    Candidates stay within the same source regime so provenance (e.g. a quake's
    centroid) is never lost by folding into a news item.
    """
    title, cat = signal.get("title"), signal.get("category")
    if not title:
        return None
    is_osint = (signal.get("source") or "").startswith("osint")
    window = datetime.now(timezone.utc) - timedelta(days=DEDUP_WINDOW_DAYS)
    q = (
        select(NarrativeEvent)
        .where(NarrativeEvent.merged_into_id.is_(None))
        .where(NarrativeEvent.category == cat)
        .where(NarrativeEvent.first_detected_at >= window)
        .order_by(NarrativeEvent.global_importance_score.desc())
        .limit(DEDUP_CANDIDATE_LIMIT)
    )
    if is_osint:
        q = q.where(NarrativeEvent.source.like("osint_%"))
    else:
        q = q.where(or_(~NarrativeEvent.source.like("osint_%"), NarrativeEvent.source.is_(None)))

    candidates = (await db.execute(q)).scalars().all()
    geo = signal.get("geography") or []
    for cand in candidates:
        matched = (
            title_dedup.is_duplicate(title, cand.canonical_title, geo, cand.geographic_relevance)
            if is_osint else
            title_dedup.same_story_exact(title, cand.canonical_title)
        )
        if matched:
            return cand
    return None


def _corroborate(canonical: NarrativeEvent, signal: dict, now: datetime) -> None:
    """Fold a duplicate signal into its canonical: keep the strongest importance,
    refresh recency, and let a higher-priority status win."""
    canonical.global_importance_score = max(canonical.global_importance_score or 0.0, signal["importance"])
    if signal.get("status") == "escalating":
        canonical.current_status = "escalating"
    canonical.last_updated_at = now


async def _upsert(signal: dict, db, require_geo: bool = True) -> bool:
    """Create or refresh a NarrativeEvent from a Signal. Returns True if a new
    canonical (feed-visible) event was created.

    Geo sources require coordinates; non-geo sources (require_geo=False) are stored
    with null centroid (they contribute sector exposure but never plot on the map).
    Near-duplicates of a recent event are stored for provenance but pointed at that
    canonical via merged_into_id, so the feed/map shows the story once.
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
        # A re-fetch of the same doc. If it was folded into a canonical, push the
        # refresh up to that canonical; otherwise refresh the event itself.
        if existing.merged_into_id:
            canonical = await db.get(NarrativeEvent, existing.merged_into_id)
            if canonical:
                _corroborate(canonical, signal, now)
                db.add(canonical)
        else:
            existing.global_importance_score = signal["importance"]
            existing.current_status = signal["status"]
            existing.last_updated_at = now
            db.add(existing)
        return False

    # New doc — fold it into a recent same-story event if one exists.
    canonical = await _find_duplicate(signal, db)
    if canonical is not None:
        _corroborate(canonical, signal, now)
        db.add(canonical)
        # Persist the duplicate (provenance + so the next re-fetch short-circuits on
        # the exact (source, external_id) match) but hide it behind the canonical.
        db.add(NarrativeEvent(
            id=uuid.uuid4(),
            canonical_title=signal["title"],
            canonical_summary=signal.get("summary"),
            category=signal["category"],
            global_importance_score=signal["importance"],
            current_status=signal["status"],
            geographic_relevance=signal.get("geography") or [],
            geo_centroid_lat=signal.get("lat"),
            geo_centroid_lng=signal.get("lng"),
            first_detected_at=now,
            last_updated_at=now,
            is_mapped=True,
            is_importance_scored=True,
            source=sid,
            external_id=ext,
            merged_into_id=canonical.id,
        ))
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
