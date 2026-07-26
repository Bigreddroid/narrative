"""
End-to-end check of the delivery path against a REAL database. Run from repo root
(inside narrativev5-api-1 locally):
    python -m backend.workers.digest_worker_test

The three properties under test are the three ways an email system hurts people, and
each is verified by observing behaviour rather than by reading the code:

  1. FAIL CLOSED — with EMAIL_SEND_ENABLED off, nothing is handed to SMTP at all, and
     the worker says why instead of looking like a silent no-op.
  2. NO DUPLICATES — running the worker three times in one window sends once. The
     existing push path re-sends the same alert for ~35 minutes; that must not be
     inherited here.
  3. ONE BAD RECIPIENT COSTS ONE RECIPIENT — a send that raises on recipient 2 of 5
     still delivers 3, 4 and 5, and records the failure with its error.

Only the socket-level ``_blocking_send`` is stubbed. The flag check, the dedup key,
the SAVEPOINT isolation, the assembly and every database write are the real ones. It
creates its own org, user, sites and list, and deletes them again.
"""

import sys, uuid, asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.config import get_settings
from backend.services import mailer
from backend.workers import digest_worker

s = get_settings()
passed = failed = 0


def ok(n, c, extra=""):
    global passed, failed
    if c:
        passed += 1
        print("  ok  " + n)
    else:
        failed += 1
        print("  XX  " + n + "  " + str(extra)[:300])


def run_worker():
    """One worker run, on its own event loop, leaving no pooled connections behind.

    ``asyncio.run`` closes its loop, but the app's shared engine keeps the asyncpg
    connections it opened — and an asyncpg connection cannot be awaited on a later
    loop. Disposing the pool inside the loop that created it is what makes running
    the worker three times in a row (the whole point of the dedupe test) possible.
    """
    async def _go():
        from backend.database import engine
        try:
            return await digest_worker.run_digest_worker()
        finally:
            await engine.dispose()
    return asyncio.run(_go())


def direct(fn):
    async def _go():
        eng = create_async_engine(s.database_url, poolclass=NullPool)
        try:
            async with eng.begin() as conn:
                return await fn(conn)
        finally:
            await eng.dispose()
    return asyncio.run(_go())


ORG = uuid.uuid4()
LIST = uuid.uuid4()
SUB = uuid.uuid4()
SUFFIX = uuid.uuid4().hex[:8]
RECIPIENTS = [f"r{i}-{SUFFIX}@narrative.test" for i in range(1, 6)]


async def _seed(conn):
    await conn.execute(text(
        "INSERT INTO organizations (id,name,slug,is_active) VALUES (:i,'Digest Co',:s,true)"),
        {"i": ORG, "s": "digest-" + SUFFIX})
    # Two sites with coordinates so assembly has somewhere to score against.
    for name, lat, lng in (("Bengaluru Campus", 12.97, 77.59), ("London Bridge", 51.50, -0.09)):
        await conn.execute(text(
            "INSERT INTO sites (id,org_id,name,lat,lng,country,is_active) "
            "VALUES (:i,:o,:n,:a,:g,'India',true)"),
            {"i": uuid.uuid4(), "o": ORG, "n": name, "a": lat, "g": lng})
    await conn.execute(text(
        "INSERT INTO distribution_lists (id,org_id,name,is_active) VALUES (:i,:o,'GSOC',true)"),
        {"i": LIST, "o": ORG})
    for r in RECIPIENTS:
        await conn.execute(text(
            "INSERT INTO distribution_members (id,list_id,email,is_active) VALUES (:i,:l,:e,true)"),
            {"i": uuid.uuid4(), "l": LIST, "e": r})
    await conn.execute(text(
        "INSERT INTO alert_subscriptions "
        "(id,org_id,list_id,channel,scope,min_severity,cadence,is_active) "
        "VALUES (:i,:o,:l,'email','org','minimal','daily',true)"),
        {"i": SUB, "o": ORG, "l": LIST})


async def _deliveries(conn):
    rows = (await conn.execute(text(
        "SELECT recipient,status,error,dedup_key FROM deliveries WHERE org_id=:o "
        "ORDER BY recipient"), {"o": ORG})).all()
    return [tuple(r) for r in rows]


direct(_seed)

# Force the cadence to be due regardless of the clock — the send hour is a scheduling
# decision, not the behaviour under test here.
digest_worker._is_due = lambda now, cadence, hour: True

# ── 1. fail closed ───────────────────────────────────────────────────────────
s.email_send_enabled = False
attempted = []
mailer._blocking_send = lambda *a, **k: attempted.append(a[5])

r1 = run_worker()
ok("with sending disabled, SMTP is never touched", attempted == [], attempted)
ok("the worker reports WHY it sent nothing, rather than looking like a no-op",
   "disabled" in str(r1.get("sending")), r1.get("sending"))
rows = direct(_deliveries)
# Scoped to THIS test's org, never to the worker's global counters. The database is
# shared — a real subscription belonging to someone else makes a global count wrong,
# and a test that only passes on an empty database is not testing the live path.
ok("all five recipients are assembled and logged", len(rows) == 5, len(rows))
ok("every delivery is recorded as SUPPRESSED, not sent and not failed",
   len(rows) == 5 and all(x[1] == "suppressed" for x in rows), rows)
ok("suppression carries its reason", all("disabled" in (x[2] or "") for x in rows), rows)

# ── 2. no duplicates ─────────────────────────────────────────────────────────
r2 = run_worker()
r3 = run_worker()
rows = direct(_deliveries)
ok("running three times in one window still produces one row per recipient",
   len(rows) == 5, len(rows))
ok("the repeat runs report the dedupe rather than silently skipping",
   r2["deduped"] >= 5 and r3["deduped"] >= 5, (r2["deduped"], r3["deduped"]))
ok("...and send nothing on the repeat runs",
   r2["sent"] == 0 and r3["sent"] == 0, (r2["sent"], r3["sent"]))
ok("dedup keys are unique per recipient", len({x[3] for x in rows}) == 5)

# ── 3. one bad recipient costs one recipient ─────────────────────────────────
# Clear the log so this window's dedup keys do not mask the new attempt.
direct(lambda c: c.execute(text("DELETE FROM deliveries WHERE org_id=:o"), {"o": ORG}))

s.email_send_enabled = True
s.smtp_host = "localhost"
s.email_from_address = "digest@narrative.test"
sent, target = [], RECIPIENTS[1]


def _stub(host, port, user, password, sender, recipient, subject, text_body, html_body):
    if recipient == target:
        raise ConnectionRefusedError("mailbox unavailable")
    sent.append(recipient)


mailer._blocking_send = _stub
r4 = run_worker()
rows = direct(_deliveries)
by_status = {x[0]: x[1] for x in rows}

ok("a send that raises does not stop the run", r4["sent"] == 4, r4)
ok("the other four are delivered", sorted(sent) == sorted(r for r in RECIPIENTS if r != target),
   sent)
ok("recipients AFTER the failure still get theirs (SAVEPOINT isolation)",
   all(by_status.get(r) == "sent" for r in RECIPIENTS[2:]), by_status)
ok("the failure is recorded, not swallowed", by_status.get(target) == "failed", by_status)
ok("the failure carries its error",
   any("ConnectionRefused" in (x[2] or "") for x in rows if x[0] == target), rows)
ok("all five recipients have a row either way", len(rows) == 5, len(rows))
ok("a successful send is stamped with a time",
   direct(lambda c: c.execute(text(
       "SELECT count(*) FROM deliveries WHERE org_id=:o AND status='sent' AND sent_at IS NOT NULL"),
       {"o": ORG})).scalar_one() == 4)

# ── content: the half no incumbent sends ─────────────────────────────────────
subj, body, html = digest_worker._render(
    "Wipro", "2026-07-26",
    [{"id": "1", "title": "Protest at gate 3", "site": "Bengaluru Campus", "km": 4.2, "outlets": 3}],
    [{"title": "Unconfirmed road closure", "reason": "Single source only — did not meet the two-outlet bar."}],
    2, None)
ok("the digest names what was escalated", "Protest at gate 3" in body)
ok("the digest also reports what was HELD, with the reason",
   "HELD, AND WHY" in body and "Single source only" in body, body[:200])
ok("an empty escalation list still says so plainly",
   "Nothing crossed your escalation bar" in
   digest_worker._render("W", "d", [], [], 1, None)[1])
ok("with no unsubscribe URL configured, no broken link is rendered",
   "http" not in body.split("Stop receiving")[-1] if "Stop receiving" in body else True)
ok("the HTML alternative escapes untrusted titles",
   "&lt;script&gt;" in digest_worker._render(
       "W", "d", [{"id": "1", "title": "<script>x</script>", "site": "S", "km": 1.0, "outlets": 2}],
       [], 1, None)[2])

# ── the window key is the identity of the period ─────────────────────────────
now = datetime(2026, 7, 26, 9, tzinfo=timezone.utc)
ok("daily windows key on the date", digest_worker._window_key(now, "daily") == "2026-07-26")
ok("weekly windows key on the ISO week",
   digest_worker._window_key(now, "weekly").startswith("2026-W"))


async def _cleanup(conn):
    await conn.execute(text("DELETE FROM deliveries WHERE org_id=:o"), {"o": ORG})
    await conn.execute(text("DELETE FROM alert_subscriptions WHERE org_id=:o"), {"o": ORG})
    await conn.execute(text("DELETE FROM distribution_members WHERE list_id=:l"), {"l": LIST})
    await conn.execute(text("DELETE FROM distribution_lists WHERE org_id=:o"), {"o": ORG})
    await conn.execute(text("DELETE FROM sites WHERE org_id=:o"), {"o": ORG})
    await conn.execute(text("DELETE FROM organizations WHERE id=:o"), {"o": ORG})


direct(_cleanup)
print("cleaned up")
print("\ndigest_worker: " + str(passed) + " passed, " + str(failed) + " failed")
raise SystemExit(1 if failed else 0)
