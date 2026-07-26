"""
digest_worker — assembles a per-subscription digest and delivers it by email.

Run standalone:  python -m backend.workers.digest_worker

WHAT MAKES THIS DIGEST DIFFERENT. It reports what we ESCALATED and, beside it, what
we HELD and why. Every incumbent's email lists what they decided to tell you; none of
them tells you what they saw and chose not to send. A signal held because only one
outlet carried it is exactly the thing a security lead needs to know exists — and it
is the one claim our engine can make that a wire-copy aggregator cannot. Suppressing
the suppression log would throw away the entire argument.

THREE SAFETY PROPERTIES, each with a specific failure it prevents:

  1. FAIL CLOSED. Sending goes through services/mailer.py, which refuses unless
     ``email_send_enabled`` is True. Local Docker and Railway both run a scheduler and
     this repo has no leader election, so without the flag BOTH would email the same
     people. With it off the worker still assembles, still logs, and records the
     deliveries as `suppressed` — so the pipeline is observable long before it is live.

  2. DEDUPLICATED IN THE DATABASE. Every delivery carries a UNIQUE dedup_key of
     sha256(subscription | window | content root). Run this three times in one window
     and you get one row per recipient, not three emails. Explicitly NOT the pattern
     of alert_worker.py:116-124, which has no key and a 35-minute lookback on a
     10-minute interval, so it re-sends for ~35 minutes.

  3. ONE BAD RECIPIENT COSTS ONE RECIPIENT. Each is written inside its own
     ``begin_nested()`` SAVEPOINT (the hazard_ingest_worker.py:306-331 precedent), so
     an IntegrityError on recipient 2 cannot poison the session and silently drop 3,
     4 and 5. A failure is written to the log with its error rather than swallowed the
     way cost_alert.py:46-47 swallows one.

Content is computed in Python from data we hold — sites, events, article outlets — and
deliberately does not try to reproduce the deck's scoring libs. Where it cannot compute
something it omits it rather than approximating; an email that quietly disagrees with
the board it links to is worse than a shorter email.
"""

import asyncio
import hashlib
import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.config import get_settings
from backend.database import AsyncSessionLocal
from backend.models.article import Article
from backend.models.delivery import (
    AlertSubscription, Delivery, DistributionList, DistributionMember,
)
from backend.models.narrative_event import NarrativeEvent
from backend.models.organization import Organization
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.site import Site
from backend.models.source import Source
from backend.models.user import User
from backend.services import mailer

logger = logging.getLogger(__name__)

# How near an event must be to a site to concern it. The deck attenuates by distance
# inside an event's extent; this is the blunt version, and it is stated as such in the
# email rather than dressed up as the same number.
PROXIMITY_KM = 250.0

# Minimum distinct outlets for a signal to be escalated. The two-source gate — the
# same bar the board uses. Below it, the signal goes in the HELD list with its reason.
CORROBORATION_MIN = 2

# min_severity → importance floor. The bands are severity.js's; the engine scores
# 0-100 global importance, so this is the mapping between the two vocabularies, kept
# in one place so the email and the board cannot drift apart silently.
SEVERITY_FLOOR = {
    "minimal": 0.0, "low": 25.0, "moderate": 45.0, "high": 60.0, "extreme": 80.0,
}


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R, r = 6371.0, math.pi / 180.0
    d_lat, d_lng = (lat2 - lat1) * r, (lng2 - lng1) * r
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin(d_lng / 2) ** 2)
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


def _window_key(now: datetime, cadence: str) -> str:
    """The identity of the period being reported on.

    Part of the dedup key, so "today's digest" is one thing no matter how many times
    the worker ticks inside the day. Weekly keys on the ISO week, which rolls over on
    Monday without any date arithmetic of our own to get wrong.
    """
    if cadence == "weekly":
        y, w, _ = now.isocalendar()
        return f"{y}-W{w:02d}"
    return now.strftime("%Y-%m-%d")


def _is_due(now: datetime, cadence: str, send_hour: int) -> bool:
    """Whether this cadence should go out on this tick.

    ``>=`` the send hour, not ``==``: the worker runs hourly, and an exact-hour match
    means a scheduler restart across that one tick silently skips the day entirely.
    The dedup key is what stops the looser condition sending twice.
    """
    if now.hour < send_hour:
        return False
    return cadence != "weekly" or now.weekday() == 0


def _dedup_key(subscription_id, recipient: str, window: str, content_hash: str) -> str:
    raw = f"{subscription_id}|{recipient.lower()}|{window}|{content_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _content_hash(escalated: list[dict], held_count: int) -> str:
    """Hash of what the digest actually says.

    Included in the dedup key so that a genuinely different digest in the same window
    is a different delivery — otherwise a subscription created mid-window, or a site
    added mid-week, would be silently deduped against an earlier, emptier message.
    Canonicalised (sorted ids) before hashing, following benchmark_ledger.py:37-64.
    """
    ids = sorted(str(e["id"]) for e in escalated)
    return hashlib.sha256(("|".join(ids) + f"#held:{held_count}").encode("utf-8")).hexdigest()


def _render(org_name: str, window_label: str, escalated: list[dict],
            held: list[dict], site_count: int, unsubscribe: str | None) -> tuple[str, str, str]:
    """(subject, text, html). No templating engine — see the module docstring.

    Deliberately no Jinja2 dependency for two templates: the repo has none today, and
    a digest is a heading plus two lists. If a third template appears, add one then.
    """
    n = len(escalated)
    subject = (f"[{org_name}] {n} situation{'' if n == 1 else 's'} for your attention"
               if n else f"[{org_name}] Nothing met the escalation bar")

    lines = [
        f"{org_name} — security digest, {window_label}",
        f"Scored against {site_count} site{'' if site_count == 1 else 's'} in your register.",
        "",
    ]
    if escalated:
        lines.append(f"ESCALATED ({n})")
        for e in escalated:
            lines.append(f"  - {e['title']}")
            lines.append(f"      {e['site']} · {e['km']:.0f} km · {e['outlets']} independent outlets")
    else:
        lines.append("ESCALATED (0)")
        lines.append("  Nothing crossed your escalation bar in this window.")
    lines.append("")

    # The half no incumbent sends. A zero here is meaningful too: it says we are not
    # quietly sitting on anything.
    lines.append(f"HELD, AND WHY ({len(held)})")
    if held:
        for h in held[:20]:
            lines.append(f"  - {h['title']}")
            lines.append(f"      {h['reason']}")
        if len(held) > 20:
            lines.append(f"  ...and {len(held) - 20} more.")
    else:
        lines.append("  Nothing was held back this window.")
    lines.append("")
    lines.append("Advisory only — physical response (evacuation, ground support) via partner.")
    if unsubscribe:
        lines.append(f"Stop receiving these: {unsubscribe}")
    else:
        # No link rather than a broken one. A 404 on an unsubscribe link is how a
        # sender earns a spam complaint.
        lines.append("To stop receiving these, reply to this message.")

    text = "\n".join(lines)
    esc = (lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    html_items = "".join(
        f"<li><strong>{esc(e['title'])}</strong><br>"
        f"<span style='color:#666'>{esc(e['site'])} · {e['km']:.0f} km · "
        f"{e['outlets']} independent outlets</span></li>"
        for e in escalated
    ) or "<li style='color:#666'>Nothing crossed your escalation bar in this window.</li>"
    html_held = "".join(
        f"<li>{esc(h['title'])}<br><span style='color:#666'>{esc(h['reason'])}</span></li>"
        for h in held[:20]
    ) or "<li style='color:#666'>Nothing was held back this window.</li>"
    html = (
        f"<div style='font-family:system-ui,sans-serif;max-width:640px'>"
        f"<h2 style='margin-bottom:4px'>{esc(org_name)} — security digest</h2>"
        f"<p style='color:#666;margin-top:0'>{esc(window_label)} · scored against "
        f"{site_count} site{'' if site_count == 1 else 's'}</p>"
        f"<h3>Escalated ({n})</h3><ul>{html_items}</ul>"
        f"<h3>Held, and why ({len(held)})</h3><ul>{html_held}</ul>"
        f"<p style='color:#888;font-size:12px'>Advisory only — physical response via partner."
        + (f" · <a href='{esc(unsubscribe)}'>Unsubscribe</a>" if unsubscribe else "")
        + "</p></div>"
    )
    return subject, text, html


async def _assemble(db, org_id, sub: AlertSubscription, since: datetime):
    """The digest content for one subscription: (escalated, held, site_count)."""
    sites = (await db.execute(
        select(Site).where(Site.org_id == org_id).where(Site.is_active == True)  # noqa: E712
    )).scalars().all()
    if sub.scope == "site" and sub.scope_ref:
        sites = [s for s in sites if str(s.id) == sub.scope_ref]
    elif sub.scope == "country" and sub.scope_ref:
        sites = [s for s in sites if (s.country or "").lower() == sub.scope_ref.lower()]
    # A site with no coordinates cannot be scored against a distance, so it is not
    # silently treated as if it were at 0,0.
    sites = [s for s in sites
             if isinstance(s.lat, (int, float)) and isinstance(s.lng, (int, float))]
    if not sites:
        return [], [], 0

    floor = SEVERITY_FLOOR.get(sub.min_severity, 60.0)
    events = (await db.execute(
        select(NarrativeEvent)
        .where(NarrativeEvent.first_detected_at >= since)
        .where(NarrativeEvent.geo_centroid_lat.isnot(None))
        .where(NarrativeEvent.merged_into_id.is_(None))
        .where(NarrativeEvent.global_importance_score >= floor)
    )).scalars().all()
    if not events:
        return [], [], len(sites)

    # Corroboration by DISTINCT OUTLET, in one query — five wire copies of one Reuters
    # story are one source, not five (the events route makes the same point at :99).
    outlets: dict = {}
    rows = (await db.execute(
        select(Article.narrative_event_id, Source.name)
        .outerjoin(Source, Article.source_id == Source.id)
        .where(Article.narrative_event_id.in_([e.id for e in events]))
    )).all()
    for eid, name in rows:
        outlets.setdefault(eid, set()).add(name or "Unknown")

    escalated, held = [], []
    for e in events:
        nearest, nearest_site = None, None
        for s in sites:
            d = _km(s.lat, s.lng, e.geo_centroid_lat, e.geo_centroid_lng)
            if nearest is None or d < nearest:
                nearest, nearest_site = d, s
        if nearest is None or nearest > PROXIMITY_KM:
            continue
        count = len(outlets.get(e.id, set()))
        item = {"id": e.id, "title": e.canonical_title,
                "site": nearest_site.name, "km": nearest, "outlets": count}
        if count >= CORROBORATION_MIN:
            escalated.append(item)
        else:
            # The reason is the product. "Held" without "why" is just an omission.
            held.append({**item,
                         "reason": f"Single source only — {nearest_site.name}, "
                                   f"{nearest:.0f} km. Did not meet the two-outlet bar."})

    escalated.sort(key=lambda x: x["km"])
    held.sort(key=lambda x: x["km"])
    return escalated, held, len(sites)


async def _recipients(db, sub: AlertSubscription) -> list[str]:
    if sub.user_id:
        user = await db.get(User, sub.user_id)
        return [user.email] if user and user.email else []
    if sub.list_id:
        members = (await db.execute(
            select(DistributionMember)
            .where(DistributionMember.list_id == sub.list_id)
            .where(DistributionMember.is_active == True)  # noqa: E712
            .where(DistributionMember.unsubscribed_at.is_(None))
        )).scalars().all()
        return [m.email for m in members if m.email]
    return []


async def run_digest_worker() -> dict:
    s = get_settings()
    now = datetime.now(timezone.utc)
    stats = {"subscriptions": 0, "due": 0, "recipients": 0,
             "sent": 0, "suppressed": 0, "failed": 0, "deduped": 0}

    # Reported once, up front, so a run that sends nothing still says WHY in one line
    # instead of looking like a silent no-op.
    refusal = mailer.preflight()
    stats["sending"] = "enabled" if refusal is None else f"disabled: {refusal.error}"

    async with AsyncSessionLocal() as db:
        subs = (await db.execute(
            select(AlertSubscription)
            .where(AlertSubscription.is_active == True)  # noqa: E712
            .where(AlertSubscription.channel == "email")
        )).scalars().all()
        stats["subscriptions"] = len(subs)

        for sub in subs:
            if not _is_due(now, sub.cadence, s.digest_send_hour_utc):
                continue
            stats["due"] += 1

            window = _window_key(now, sub.cadence)
            since = now - timedelta(days=7 if sub.cadence == "weekly" else 1)
            org = await db.get(Organization, sub.org_id)
            org_name = org.name if org else "Your organization"

            escalated, held, site_count = await _assemble(db, sub.org_id, sub, since)
            chash = _content_hash(escalated, len(held))

            # An empty digest is still sent. "Nothing crossed your bar today" is a
            # real answer from a system that was watching; silence is indistinguishable
            # from a system that was down, which is the exact ambiguity this product
            # exists to remove.
            for recipient in await _recipients(db, sub):
                stats["recipients"] += 1
                key = _dedup_key(sub.id, recipient, window, chash)

                existing = (await db.execute(
                    select(Delivery).where(Delivery.dedup_key == key)
                )).scalars().first()
                if existing is not None:
                    stats["deduped"] += 1
                    continue

                unsub = (f"{s.public_base_url.rstrip('/')}/unsubscribe?d={key[:32]}"
                         if s.public_base_url else None)
                subject, text, html = _render(
                    org_name, window, escalated, held, site_count, unsub)

                result = await mailer.send(recipient, subject, text, html)
                try:
                    # Per-recipient SAVEPOINT: a duplicate key or a bad row here must
                    # not roll back the recipients already recorded in this batch.
                    async with db.begin_nested():
                        db.add(Delivery(
                            org_id=sub.org_id, subscription_id=sub.id, channel="email",
                            recipient=recipient, dedup_key=key, content_hash=chash,
                            subject=subject, item_count=len(escalated),
                            status=result.status, error=result.error,
                            sent_at=now if result.sent else None,
                        ))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Delivery row for %s failed: %s", recipient, exc)
                    stats["failed"] += 1
                    continue
                stats[result.status if result.status in stats else "failed"] += 1

        # alerts_sent counts what actually left the building, not what was assembled —
        # a suppressed digest is not an alert anyone received.
        db.add(PipelineMetric(worker_name="digest_worker", alerts_sent=stats["sent"]))
        await db.commit()

    logger.info("digest_worker: %s", stats)
    return stats


if __name__ == "__main__":
    print(asyncio.run(run_digest_worker()))
