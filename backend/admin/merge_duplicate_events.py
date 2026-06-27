"""
One-off backfill: fold existing near-duplicate events into a canonical event.

The ingest-time fix (hazard_ingest_worker._upsert) only prevents *new* duplicates;
this cleans up the ones already in the DB. Greedy, per-category clustering using the
same title_dedup rule used at ingest. The highest-importance (then earliest) event
in each cluster becomes canonical; the rest get merged_into_id set and their articles
reassigned, so every feed/map query collapses the story to one row.

Dry-run by default — prints what it would merge. Pass --apply to write.

    python -m backend.admin.merge_duplicate_events                 # preview
    python -m backend.admin.merge_duplicate_events --apply         # commit
    python -m backend.admin.merge_duplicate_events --window-days 60 --apply
"""

import argparse
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from backend.consequence_engine import title_dedup
from backend.database import AsyncSessionLocal
from backend.models.article import Article
from backend.models.narrative_event import NarrativeEvent

logger = logging.getLogger(__name__)


def _is_osint(e: NarrativeEvent) -> bool:
    return (e.source or "").startswith("osint")


def _osint_match(a: NarrativeEvent, b: NarrativeEvent) -> bool:
    return title_dedup.is_duplicate(a.canonical_title, b.canonical_title,
                                    a.geographic_relevance, b.geographic_relevance)


def _exact_match(a: NarrativeEvent, b: NarrativeEvent) -> bool:
    return title_dedup.same_story_exact(a.canonical_title, b.canonical_title)


def _plan_merges(events: list[NarrativeEvent], matcher) -> list[tuple[NarrativeEvent, NarrativeEvent]]:
    """Return [(duplicate, canonical), …] greedily grouping events within each category
    using `matcher(dup, canonical) -> bool`."""
    by_cat: dict[str | None, list[NarrativeEvent]] = defaultdict(list)
    for e in events:
        by_cat[e.category].append(e)

    far_future = datetime.max.replace(tzinfo=timezone.utc)
    merges: list[tuple[NarrativeEvent, NarrativeEvent]] = []
    for evs in by_cat.values():
        # Canonical preference: highest importance, then earliest detection (stable).
        evs.sort(key=lambda e: (-(e.global_importance_score or 0.0),
                                 e.first_detected_at or far_future))
        canonicals: list[NarrativeEvent] = []
        for e in evs:
            match = next((c for c in canonicals if matcher(e, c)), None)
            if match is not None:
                merges.append((e, match))
            else:
                canonicals.append(e)
    return merges


async def run(apply: bool, window_days: int) -> dict:
    window = datetime.now(timezone.utc) - timedelta(days=window_days)
    async with AsyncSessionLocal() as db:
        events = (await db.execute(
            select(NarrativeEvent)
            .where(NarrativeEvent.merged_into_id.is_(None))
            .where(NarrativeEvent.first_detected_at >= window)
        )).scalars().all()

        # OSINT/news → fuzzy match; structured feeds (USGS/GDACS/NWS/launches) →
        # exact-title only (their templated titles look similar but are distinct
        # events, so fuzzy matching would merge separate quakes/launches).
        osint = [e for e in events if _is_osint(e)]
        structured = [e for e in events if not _is_osint(e)]
        merges = _plan_merges(osint, _osint_match) + _plan_merges(structured, _exact_match)

        # Group for a readable preview: canonical title -> folded titles.
        groups: dict[str, list[str]] = defaultdict(list)
        for dup, canon in merges:
            groups[canon.canonical_title].append(dup.canonical_title)

        print(f"Scanned {len(events)} live events (last {window_days}d). "
              f"{len(merges)} duplicates across {len(groups)} stories would be folded.\n")
        for canon_title, dups in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:25]:
            print(f"  [{len(dups) + 1}x] {canon_title[:80]}")
            for d in dups[:4]:
                print(f"         + {d[:76]}")
            if len(dups) > 4:
                print(f"         + ... +{len(dups) - 4} more")

        if not apply:
            print("\n(dry run -- pass --apply to commit)")
            return {"scanned": len(events), "merged": 0, "stories": len(groups)}

        for dup, canon in merges:
            await db.execute(
                update(Article).where(Article.narrative_event_id == dup.id)
                .values(narrative_event_id=canon.id)
            )
            canon.global_importance_score = max(
                canon.global_importance_score or 0.0, dup.global_importance_score or 0.0)
            dup.merged_into_id = canon.id
            db.add(canon)
            db.add(dup)
        await db.commit()
        print(f"\nApplied: folded {len(merges)} duplicates into {len(groups)} canonical events.")
        return {"scanned": len(events), "merged": len(merges), "stories": len(groups)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="commit the merges (default: dry run)")
    ap.add_argument("--window-days", type=int, default=30, help="only consider events newer than this")
    args = ap.parse_args()
    asyncio.run(run(args.apply, args.window_days))
