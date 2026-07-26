"""Repair stored Google News redirect URLs into real publisher URLs.

Every article ingested from the Google News feeds before the resolver existed carries
`news.google.com/rss/articles/CBMi…` as its URL and `news.google.com` as its outlet. In
the signal drawer that is a "source document" link that lands on a Google interstitial
instead of the article, attributed to an aggregator instead of a publisher — an evidence
chain an analyst cannot follow.

An earlier note recorded these rows as unrepairable, on the premise that the redirect was
"the only address we have". That premise was wrong: the publisher URL is recoverable from
the stored redirect alone (see backend/feeds/gnews_resolve.py), so these rows can be
fixed in place.

Both the URL and the outlet are rewritten:
  • url + url_hash  → the resolved publisher URL. If a row for that URL already exists
    (the same story also arrived via a direct feed) the Google row is left alone and
    reported as a collision — merging evidence rows is a different decision, taken with
    eyes open, not a side effect of a link repair.
  • source_id → a Source named for the resolved host ('nytimes.com'). The host is a fact
    derived from the address. A display name ("The New York Times") is NOT invented here.

Idempotent: rows already carrying a publisher URL are not matched by the query.

  python -m scripts.backfill_gnews_urls --dry-run
  python -m scripts.backfill_gnews_urls --limit 500
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import uuid
from collections import defaultdict
from urllib.parse import urlparse

from sqlalchemy import func, select, update

from backend.database import AsyncSessionLocal
from backend.feeds import gnews_resolve
from backend.models.article import Article
from backend.models.source import Source

logger = logging.getLogger(__name__)

_PATTERN = "%news.google.com/rss/articles/%"


async def _known_names_by_host(db) -> dict[str, str]:
    """host → the outlet name this database ALREADY uses for that host.

    Naming a repaired row by its bare domain would be accurate but would split one
    publisher in two wherever a direct feed already covers it ('The Guardian' from the
    feed, 'theguardian.com' from the repair). Corroboration counts DISTINCT OUTLET, so
    that split would manufacture a second "independent" source on the same event.

    So the name is taken from evidence already in the table: articles stored under
    source 'Deutsche Welle' have dw.com URLs, therefore dw.com's outlet is 'Deutsche
    Welle'. Most frequent name wins, ties broken alphabetically so a re-run is
    deterministic. Only hosts we have never seen fall back to the bare domain.
    """
    rows = (await db.execute(
        select(Article.url, Source.name).join(Source, Source.id == Article.source_id)
    )).all()
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for url, name in rows:
        host = gnews_resolve.publisher_from_url(url)
        # An aggregator label is what we are repairing away from; never adopt it.
        if host and name and "news.google.com" not in name:
            counts[host][name] += 1
    return {host: sorted(names.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            for host, names in counts.items()}


async def _publisher_source(db, host: str, known: dict[str, str]) -> Source:
    """The Source row for a publisher host, reusing this database's existing name for
    that host when it has one, else creating a row named for the host itself."""
    name = known.get(host, host)
    # sources.name is NOT unique (three names are duplicated in this database today), so
    # this must tolerate more than one match instead of raising. Ordered for determinism.
    row = (await db.execute(
        select(Source).where(Source.name == name).order_by(Source.id).limit(1)
    )).scalars().first()
    if row is None:
        # url is populated (unlike feed-label sources) so a future dedupe can key on host.
        row = Source(id=uuid.uuid4(), name=name, url=f"https://{host}", is_active=True)
        db.add(row)
        await db.flush()
    return row


async def _measure_outlet_split(db) -> list[tuple[str, int]]:
    """Corroboration counts DISTINCT OUTLET, so renaming a backfilled row's outlet could
    in principle make one publisher look like two on the same event ('The Guardian' from
    a direct feed plus 'theguardian.com' from a repaired Google row) — which would
    manufacture corroboration. This measures that directly: events carrying two or more
    articles whose URLs share a host but whose Source names differ.
    """
    rows = (await db.execute(
        select(Article.narrative_event_id, Article.url, Source.name)
        .join(Source, Source.id == Article.source_id)
        .where(Article.narrative_event_id.isnot(None))
    )).all()
    by_event: dict[object, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for event_id, url, name in rows:
        host = gnews_resolve.publisher_from_url(url)
        if host:
            by_event[event_id][host].add(name)
    return [(str(eid), len(names))
            for eid, hosts in by_event.items()
            for _host, names in hosts.items() if len(names) > 1]


async def run(limit: int, dry_run: bool) -> dict:
    stats = {"candidates": 0, "resolved": 0, "updated": 0, "collisions": 0,
             "unresolved": 0, "outlet_splits": 0}
    async with AsyncSessionLocal() as db:
        total = (await db.execute(
            select(func.count()).select_from(Article).where(Article.url.like(_PATTERN))
        )).scalar_one()
        rows = (await db.execute(
            select(Article.id, Article.url).where(Article.url.like(_PATTERN)).limit(limit)
        )).all()
        stats["candidates"] = len(rows)
        print(f"{total} article(s) still carry a Google News redirect; taking {len(rows)}")
        if not rows:
            return stats
        stats["outlet_splits_before"] = len(await _measure_outlet_split(db))
        print(f"same-publisher-two-names on one event BEFORE: {stats['outlet_splits_before']}")

        known = await _known_names_by_host(db)
        print(f"{len(known)} host(s) already have an outlet name in this database")
        urls = [u for _id, u in rows]
        resolved = await gnews_resolve.resolve_urls(urls, budget=len(urls))
        stats["resolved"] = len(resolved)
        stats["unresolved"] = len(set(urls)) - len(resolved)
        print(f"resolved {len(resolved)}/{len(set(urls))} distinct URLs")

        for art_id, old_url in rows:
            new_url = resolved.get(old_url)
            if not new_url:
                continue
            host = gnews_resolve.publisher_from_url(new_url)
            if not host:
                continue
            new_hash = hashlib.sha256(new_url.encode("utf-8")).hexdigest()
            clash = (await db.execute(
                select(Article.id).where(Article.url_hash == new_hash)
                .where(Article.id != art_id)
            )).scalar_one_or_none()
            if clash is not None:
                stats["collisions"] += 1
                continue
            src = await _publisher_source(db, host, known)
            await db.execute(update(Article).where(Article.id == art_id).values(
                url=new_url, url_hash=new_hash, source_id=src.id))
            stats["updated"] += 1

        # Measured INSIDE the transaction, before commit-or-rollback, so --dry-run
        # reports the state the writes would actually produce rather than the state we
        # started from. A rise here means the repair split a publisher in two.
        stats["outlet_splits"] = len(await _measure_outlet_split(db))

        if dry_run:
            await db.rollback()
            print("DRY RUN — rolled back")
        else:
            await db.commit()

    print(f"\ncandidates={stats['candidates']} resolved={stats['resolved']} "
          f"updated={stats['updated']} collisions={stats['collisions']} "
          f"unresolved={stats['unresolved']}")
    before = stats.get("outlet_splits_before", 0)
    delta = stats["outlet_splits"] - before
    print(f"same-publisher-two-names on one event: {before} -> {stats['outlet_splits']} "
          f"(delta {delta:+d}) "
          f"{'— this repair added none' if delta <= 0 else '— REVIEW: the repair split a publisher'}")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=1000,
                    help="max rows to attempt (each costs a ~600KB fetch)")
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve and report, write nothing")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(run(args.limit, args.dry_run))


if __name__ == "__main__":
    main()
