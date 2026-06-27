"""
Backfill: re-run deterministic synthesis on free-feed events whose consequence map
is thin or missing predictions, so the live feed shows full 3-step chains AND
concrete predictions (the synthesize() change only affects newly-ingested events).

Scope = free-feed/OSINT events only (source IS NOT NULL): those were synthesized
deterministically anyway, so re-synth is loss-less. Article/LLM-clustered events
(source IS NULL) may carry richer maps and are left untouched.

Targets a map when prediction_score is NULL or the chain has < 3 steps. Dry-run by
default; pass --apply to write.

    python -m backend.admin.resynthesize_maps            # preview
    python -m backend.admin.resynthesize_maps --apply    # commit
"""

import argparse
import asyncio
import logging
import uuid

from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.feeds import synthesize as S
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.narrative_event import NarrativeEvent

logger = logging.getLogger(__name__)


def _signal_from(ev: NarrativeEvent) -> dict:
    return {
        "title": ev.canonical_title,
        "summary": ev.canonical_summary,
        "category": ev.category or "disaster",
        "importance": ev.global_importance_score or 50,
        "geography": ev.geographic_relevance or [],
        "source": ev.source or "feed",
    }


def _is_thin(m: EventConsequenceMap | None) -> bool:
    if m is None:
        return True
    if m.prediction_score is None:
        return True
    chain = m.consequence_chain
    return not isinstance(chain, list) or len(chain) < 3


async def run(apply: bool) -> dict:
    scanned = updated = created = 0
    async with AsyncSessionLocal() as db:
        events = (await db.execute(
            select(NarrativeEvent)
            .where(NarrativeEvent.merged_into_id.is_(None))
            .where(NarrativeEvent.source.isnot(None))
        )).scalars().all()

        for ev in events:
            scanned += 1
            latest = (await db.execute(
                select(EventConsequenceMap)
                .where(EventConsequenceMap.narrative_event_id == ev.id)
                .where(EventConsequenceMap.is_suppressed == False)  # noqa: E712
                .order_by(EventConsequenceMap.version.desc())
                .limit(1)
            )).scalar_one_or_none()

            if not _is_thin(latest):
                continue

            syn = S.synthesize(_signal_from(ev))
            if latest is None:
                created += 1
                if apply:
                    db.add(EventConsequenceMap(
                        id=uuid.uuid4(), narrative_event_id=ev.id, version=1,
                        consensus_summary=syn["consensus_summary"],
                        consequence_chain=syn["consequence_chain"],
                        direct_impact=syn["direct_impact"], indirect_impact=syn["indirect_impact"],
                        confidence=syn["confidence"], disputed_points=syn["disputed_points"],
                        sources_analyzed=syn["sources_analyzed"],
                        prediction_score=syn["prediction_score"],
                        prediction_reasoning=syn["prediction_reasoning"],
                    ))
            else:
                updated += 1
                if apply:
                    latest.consequence_chain = syn["consequence_chain"]
                    latest.direct_impact = syn["direct_impact"]
                    latest.indirect_impact = syn["indirect_impact"]
                    latest.prediction_score = syn["prediction_score"]
                    latest.prediction_reasoning = syn["prediction_reasoning"]
                    if not latest.consensus_summary:
                        latest.consensus_summary = syn["consensus_summary"]
                    db.add(latest)

        if apply:
            await db.commit()

    verb = "Re-synthesized" if apply else "Would re-synthesize"
    print(f"Scanned {scanned} free-feed events. {verb} {updated} thin maps "
          f"(+{created} missing maps).{'' if apply else '  (dry run -- pass --apply)'}")
    return {"scanned": scanned, "updated": updated, "created": created}


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="commit the re-synth (default: dry run)")
    args = ap.parse_args()
    asyncio.run(run(args.apply))
