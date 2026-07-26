"""
advisory_worker — keeps the advice library current from official government sources.

Run standalone:  python -m backend.workers.advisory_worker

Two authorities, both keyless. The State Department publishes all ~213 countries in
one RSS document, so that leg costs a single request no matter how many countries a
customer has. The FCDO publishes one document per country, so that leg is fetched
ONLY for countries a customer actually has a site or a trip in — polling 200 country
pages every six hours to serve a register of eight would be rude to a public service
we depend on and are not paying for.

Idempotent by content hash: an unchanged sheet is not rewritten. When a sheet DOES
change, the previous row is marked superseded rather than deleted, because a
duty-of-care team has to be able to answer "what did that government say at the time
we sent our people" after the fact, and an UPDATE in place destroys that evidence.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from backend.countries import to_iso2
from backend.database import AsyncSessionLocal
from backend.feeds import advisories as feed
from backend.models.advisory import Advisory
from backend.models.person import Trip
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.site import Site

logger = logging.getLogger(__name__)

# Fetched even with an empty register, so a fresh install has a library rather than a
# blank page — chosen as the places this product's buyers most often operate, not as
# an assessment of anywhere. The State leg covers every country regardless.
SEED_COUNTRIES = [
    "India", "United Arab Emirates", "Saudi Arabia", "United Kingdom",
    "United States", "Germany", "Romania", "Singapore", "Philippines", "Mexico",
]


def _hash(item: dict) -> str:
    """The identity of an ADVISORY — the issuer's level and publication date.

    🔴 Deliberately NOT a hash of the summary text, and this was measured rather than
    assumed. The State Department RSS serves materially different bodies for the same
    country on consecutive requests: three different Barbados summaries in one
    afternoon, one of them reading "Summary not available". Hashing the text turned
    that instability into fake history — a security team would have read "the US
    changed its advice three times today" when it had not changed it at all.

    So identity comes from what the ISSUER says identifies the advisory: its level and
    the date it published. Those are the government's own statement about when its
    advice changed, and they are stable across the flapping. ``fetched_at`` is excluded
    for the same reason it always was — a timestamp in the key makes every poll a change.
    """
    published = item.get("published_at")
    payload = json.dumps({
        "level_code": item.get("level_code"),
        "published": published.date().isoformat() if published else None,
        "url": item.get("url"),
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _customer_countries(db) -> list[str]:
    """Countries a customer actually has people or property in."""
    seen, out = set(), []
    site_rows = (await db.execute(
        select(Site.country).where(Site.is_active == True).where(Site.country.isnot(None))  # noqa: E712
    )).scalars().all()
    trip_rows = (await db.execute(
        select(Trip.to_country).where(Trip.is_active == True).where(Trip.to_country.isnot(None))  # noqa: E712
    )).scalars().all()
    for c in list(site_rows) + list(trip_rows) + SEED_COUNTRIES:
        key = (c or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(c.strip())
    return out


async def _store(db, item: dict) -> str:
    """Write one advisory. Returns 'new', 'unchanged' or 'skipped'."""
    if not item or not item.get("country"):
        return "skipped"
    chash = _hash(item)

    existing = (await db.execute(
        select(Advisory)
        .where(Advisory.authority == item["authority"])
        .where(Advisory.country == item["country"])
        .where(Advisory.content_hash == chash)
    )).scalars().first()
    if existing is not None:
        # Same advisory. If this snapshot of it is fuller than the one we hold, take
        # the text — the source alternates between complete bodies and stubs like
        # "Summary not available", and a customer should always see the most complete
        # version the government actually published, without it counting as a change.
        new_summary = item.get("summary") or ""
        new_sections = item.get("sections") or {}
        if len(new_summary) > len(existing.summary or ""):
            existing.summary = new_summary
        if len(json.dumps(new_sections)) > len(json.dumps(existing.sections or {})):
            existing.sections = new_sections
        existing.level_label = item.get("level_label") or existing.level_label
        db.add(existing)
        return "unchanged"

    # 🔴 Which row is CURRENT is decided by the issuer's publication date, never by
    # which snapshot happened to arrive last. The State RSS rotates between cached
    # snapshots, so arrival order is effectively random — and "current" flipping
    # between two dates on every poll would mean the level shown to a customer
    # depended on when they refreshed the page.
    newest = (await db.execute(
        select(Advisory.published_at)
        .where(Advisory.authority == item["authority"])
        .where(Advisory.country == item["country"])
        .order_by(Advisory.published_at.desc().nullslast())
        .limit(1)
    )).scalars().first()

    published = item.get("published_at")
    is_newest = newest is None or (published is not None and published >= newest)

    if is_newest:
        # Supersede rather than delete. The old text is the record of what we could
        # have known at the time, and it is the only thing that can answer a question
        # asked after an incident.
        await db.execute(
            update(Advisory)
            .where(Advisory.authority == item["authority"])
            .where(Advisory.country == item["country"])
            .where(Advisory.is_current == True)  # noqa: E712
            .values(is_current=False)
        )

    db.add(Advisory(
        authority=item["authority"], country=item["country"],
        country_iso=to_iso2(item["country"]),
        level_code=item.get("level_code"), level_label=item.get("level_label"),
        summary=item.get("summary"), sections=item.get("sections") or {},
        url=item.get("url"), published_at=published,
        content_hash=chash, is_current=is_newest,
    ))
    return "new"


async def run_advisory_worker() -> dict:
    stats = {"state_fetched": 0, "fcdo_fetched": 0, "new": 0, "unchanged": 0,
             "skipped": 0, "authorities": 0}

    async with AsyncSessionLocal() as db:
        wanted = await _customer_countries(db)
        wanted_keys = {c.lower() for c in wanted}

        # One request for every country the State Department publishes.
        state_items = await feed.fetch_state_dept()
        stats["state_fetched"] = len(state_items)
        if state_items:
            stats["authorities"] += 1
        for item in state_items:
            try:
                # Per-item SAVEPOINT: one malformed sheet must not cost the other 212.
                async with db.begin_nested():
                    stats[await _store(db, item)] += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Advisory store failed for %s: %s", item.get("country"), exc)
                stats["skipped"] += 1

        # One request per country we actually cover — see the module docstring.
        fcdo_any = False
        for country in wanted:
            doc = await feed.fetch_fcdo(country)
            if doc is None:
                continue
            fcdo_any = True
            stats["fcdo_fetched"] += 1
            try:
                async with db.begin_nested():
                    stats[await _store(db, doc)] += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("FCDO store failed for %s: %s", country, exc)
                stats["skipped"] += 1
            # Deliberately polite to a free public API we do not pay for.
            await asyncio.sleep(0.3)
        if fcdo_any:
            stats["authorities"] += 1

        db.add(PipelineMetric(worker_name="advisory_worker",
                              articles_scraped=stats["state_fetched"] + stats["fcdo_fetched"]))
        await db.commit()

    # Said out loud: a run where neither authority answered has produced nothing, and
    # must not be mistaken for a run that found nothing to update.
    if stats["authorities"] == 0:
        logger.warning("advisory_worker: NO authority answered — the library is unchanged, "
                       "not confirmed current")
    logger.info("advisory_worker: %s", stats)
    return stats


if __name__ == "__main__":
    print(asyncio.run(run_advisory_worker()))
