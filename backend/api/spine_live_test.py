"""
End-to-end check of the product spine — org, site register, import, people, trips —
against a REAL database. Run from repo root (inside narrativev5-api-1 locally):
    python -m backend.api.spine_live_test

Deliberately not a pure test. On this repo a green unit suite has coexisted with four
separate real bugs, and one route test passed while asserting over EMPTY payloads
because its DB auth had silently failed. So this one talks to Postgres through the
actual routes with a real bearer token, and it FAILS rather than skips if the database
is not there: a spine test that cannot see a database has proved nothing.

It writes its own throwaway user and organization and deletes them again, so it is
safe against a live database as well as CI's ephemeral one.

Two of the checks below exist because they caught real defects on first run:
  * a repeated site identifier was collapsing two of the customer's sites into one;
  * the same file re-imported reported updates instead of no-ops.
Both are in the plan's definition of "Phase 1 done", and both would have shipped.
"""
import sys, uuid, asyncio
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from datetime import datetime, timedelta, timezone
from jose import jwt
from fastapi.testclient import TestClient
from sqlalchemy import text

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.config import get_settings
from backend.main import app

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


def direct(fn):
    """Run a DB coroutine on its OWN engine and loop.

    The app's shared engine cannot be used here: TestClient drives the app on a
    private event loop, and an asyncpg connection pooled on one loop cannot be
    awaited on another. A throwaway NullPool engine per call keeps the two apart.
    """
    async def _go():
        eng = create_async_engine(s.database_url, poolclass=NullPool)
        try:
            async with eng.begin() as conn:
                return await fn(conn)
        finally:
            await eng.dispose()
    return asyncio.run(_go())


async def _make_user(conn):
    """A throwaway account of our own.

    Borrowing an existing user would make the run depend on whatever happens to be in
    the database, and would leave this test's organization attached to a real person.
    """
    uid = uuid.uuid4()
    email = "spine-live-" + uuid.uuid4().hex[:10] + "@narrative.test"
    await conn.execute(
        text("INSERT INTO users (id,email,password_hash,tier,created_at) "
             "VALUES (:i,:e,'x','enterprise',now())"),
        {"i": uid, "e": email})
    return uid, email


uid, email = direct(_make_user)
print("acting as " + str(email))

tok = jwt.encode({"sub": str(uid), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                 s.secret_key, algorithm="HS256")
H = {"Authorization": "Bearer " + tok}
# Entered as a context manager on purpose: a bare TestClient spins up a NEW event
# loop per request, and the app's pooled asyncpg connections cannot be awaited on a
# loop other than the one that opened them. Entering pins one portal for the run.
c = TestClient(app)
c.__enter__()

APOS = "'"
RISKY_NAME = APOS + "-Central Ops"      # as an export would write it
PLAIN_NAME = "-Central Ops"             # as it must be stored

# -- no org yet ---------------------------------------------------------------
r = c.get("/api/v1/sites", headers=H)
ok("a user with no organization is refused, not shown someone else's register",
   r.status_code == 403, r.status_code)

slug = "livecheck-" + uuid.uuid4().hex[:8]
r = c.post("/api/v1/org", headers=H, json={"name": "Live Check Co", "slug": slug})
ok("an organization can be created", r.status_code == 200, r.text)
org_id = r.json()["id"]
ok("the creator is its admin", r.json()["role"] == "admin")

r = c.post("/api/v1/org", headers=H, json={"name": "Second", "slug": slug + "-2"})
ok("a second organization for the same account is refused", r.status_code == 409, r.status_code)

# -- an empty register is EMPTY, never all-clear -------------------------------
r = c.get("/api/v1/sites", headers=H)
ok("an empty register returns no rows", r.json()["count"] == 0)
ok("an empty register reports checked=0, not a clean bill of health",
   r.json()["audit"]["checked"] == 0)

# -- import a register carrying the defects observed in the wild ---------------
CSV = (
    "Site Code,Site Name,City,Country,Latitude,Longitude,Headcount,Tier,Type\r\n"
    "AFR08,Johannesburg Campus,Johannesburg,India,-26.20,28.05,410,tier-1,campus\r\n"
    "AFR08,Johannesburg Annexe,Johannesburg,South Africa,-26.11,28.06,120,tier-2,office\r\n"
    "IND01,Electronic City,Bengaluru,India,12.84,77.66,5200,tier-1,campus\r\n"
    "IND02,Hinjewadi,Pune,India,18.59,73.73,3100,tier-1,campus\r\n"
    "IND03,Gachibowli,Hyderabad,India,17.44,78.35,,tier-2,delivery\r\n"
    "NOC01,No Country Row,Nowhere,,0,0,50,tier-3,office\r\n"
    "NAR01,Narnia Office,Cair Paravel,Narnia,51.5,-0.12,20,tier-3,office\r\n"
    "LON01," + RISKY_NAME + ",London,United Kingdom,51.50,-0.12,90,tier-2,office\r\n"
)
r = c.post("/api/v1/sites/import", headers=H, files={"file": ("register.csv", CSV, "text/csv")})
ok("the register imports", r.status_code == 200, r.text)
imp = r.json()
ok("every row is created on the first import", imp["created"] == 8, imp)
a = imp["audit"]
checks = a["by_check"]
ok("the same identifier under two countries is caught", "conflicting_country" in checks, checks)
ok("a row with no country is caught", "missing_country" in checks, checks)
ok("0,0 is caught as an import default", "null_island" in checks, checks)
ok("a site with no headcount is caught", "missing_headcount" in checks, checks)
ok("an unmapped country is caught", "unmapped_country" in checks, checks)
ok("real countries are NOT flagged unmapped (only Narnia is)",
   checks.get("unmapped_country", 0) == 1, checks)
ok("the audit is not clean", a["clean"] is False)
ok("findings name the customer's own row ids",
   any(f["site_id"] == "AFR08" for f in a["findings"]),
   [f["site_id"] for f in a["findings"]][:6])

# -- idempotency: the same file again must change nothing ----------------------
i2 = c.post("/api/v1/sites/import", headers=H,
            files={"file": ("register.csv", CSV, "text/csv")}).json()
ok("re-importing the identical file creates nothing", i2["created"] == 0, i2)
ok("re-importing the identical file updates nothing", i2["updated"] == 0, i2)
ok("re-importing reports every row unchanged", i2["unchanged"] == 8, i2)

r = c.get("/api/v1/sites", headers=H)
ok("the register still holds exactly 8 sites after two imports",
   r.json()["count"] == 8, r.json()["count"])
sites = {x["external_id"]: x for x in r.json()["sites"]}
ok("a repeated identifier keeps BOTH sites - a duplicate is reported, never merged away",
   len([x for x in r.json()["sites"] if x["external_id"] == "AFR08"]) == 2,
   [x["name"] for x in r.json()["sites"] if x["external_id"] == "AFR08"])
ok("a blank headcount is stored as NULL, not 0",
   sites["IND03"]["headcount"] is None, sites["IND03"]["headcount"])
ok("an export-escaped name is un-escaped on import",
   sites["LON01"]["name"] == PLAIN_NAME, sites["LON01"]["name"])

# -- a changed row is an update, not a duplicate -------------------------------
CSV2 = CSV.replace("77.66,5200", "77.66,5400")
i3 = c.post("/api/v1/sites/import", headers=H,
            files={"file": ("register.csv", CSV2, "text/csv")}).json()
ok("a changed headcount is an update", i3["updated"] == 1, i3)
ok("a changed row does not create a second site", i3["created"] == 0, i3)

exp = c.get("/api/v1/sites/export", headers=H)
ok("export is served as CSV",
   exp.status_code == 200 and "text/csv" in exp.headers["content-type"], exp.status_code)
ok("export re-escapes a formula-leading name", RISKY_NAME in exp.text, exp.text[:160])

# -- dry run writes nothing ----------------------------------------------------
before = c.get("/api/v1/sites", headers=H).json()["count"]
CSV3 = CSV + "NEW01,Brand New Site,Dublin,Ireland,53.35,-6.26,40,tier-3,office\r\n"
dr = c.post("/api/v1/sites/import?dry_run=true", headers=H,
            files={"file": ("register.csv", CSV3, "text/csv")}).json()
ok("a dry run reports what it would create", dr["created"] == 1, dr)
ok("a dry run writes nothing",
   c.get("/api/v1/sites", headers=H).json()["count"] == before, before)

# -- people, and the site-id join that replaces the city-name match ------------
site_ind01 = sites["IND01"]["id"]
site_afr = sites["AFR08"]["id"]
p = c.post("/api/v1/people", headers=H,
           json={"name": "A Traveller", "role": "Programme Director",
                 "home_site_id": site_ind01})
ok("a person can be created", p.status_code == 200, p.text)
pid = p.json()["id"]

t = c.post("/api/v1/people/trips", headers=H, json={
    "person_id": pid, "from_site_id": site_ind01, "to_site_id": site_afr,
    "depart_date": "2026-07-20", "return_date": "2026-08-05"})
ok("a trip can be created against a real site", t.status_code == 200, t.text)
trip = t.json()
ok("the trip carries toSiteId - the join key the deck needs",
   trip["toSiteId"] == site_afr, trip.get("toSiteId"))
ok("the trip fills `to` from the destination site when not given",
   trip["to"] == "Johannesburg", trip.get("to"))
ok("the trip is fixture-shaped",
   {"departISO", "returnISO", "lastCheckInISO", "traveler", "role", "from"} <= set(trip),
   sorted(trip))
ok("a new trip has no check-in - unaccounted for, not safe",
   trip["lastCheckInISO"] is None)

bad = c.post("/api/v1/people/trips", headers=H,
             json={"person_id": pid, "depart_date": "2026-07-20"})
ok("a trip with no destination is refused", bad.status_code == 400, bad.status_code)
rev = c.post("/api/v1/people/trips", headers=H,
             json={"person_id": pid, "to_city": "Dubai", "depart_date": "2026-08-05",
                   "return_date": "2026-07-20"})
ok("a return before the departure is refused", rev.status_code == 400, rev.status_code)

ci = c.patch("/api/v1/people/trips/" + trip["id"], headers=H, json={"check_in": True})
ok("a check-in is stamped server-side", ci.json()["lastCheckInISO"] is not None, ci.text)

lt = c.get("/api/v1/people/trips", headers=H).json()
ok("the trip list is populated", lt["count"] == 1, lt["count"])
ok("the listed trip still carries its site id", lt["trips"][0]["toSiteId"] == site_afr)

# -- cross-tenant isolation ----------------------------------------------------
async def _other_org(conn):
    oid, sid = uuid.uuid4(), uuid.uuid4()
    await conn.execute(
        text("INSERT INTO organizations (id,name,slug,is_active) VALUES (:i,'Other',:s,true)"),
        {"i": oid, "s": "other-" + uuid.uuid4().hex[:8]})
    await conn.execute(
        text("INSERT INTO sites (id,org_id,name,is_active) VALUES (:s,:o,'Their Site',true)"),
        {"s": sid, "o": oid})
    return oid, sid


oid, foreign_site = direct(_other_org)
x = c.post("/api/v1/people/trips", headers=H,
           json={"person_id": pid, "to_site_id": str(foreign_site), "depart_date": "2026-07-20"})
ok("another organization's site id cannot be attached to our traveller",
   x.status_code == 404, x.status_code)
x2 = c.patch("/api/v1/sites/" + str(foreign_site), headers=H, json={"name": "Hijacked"})
ok("another organization's site cannot be edited", x2.status_code == 404, x2.status_code)

# -- the last admin cannot be removed -----------------------------------------
mem = c.get("/api/v1/org/members", headers=H).json()["members"]
ok("the org lists its one member", len(mem) == 1, mem)
d = c.delete("/api/v1/org/members/" + mem[0]["id"], headers=H)
ok("the last admin cannot remove themselves", d.status_code == 409, d.status_code)


async def _cleanup(conn):
    for o in (org_id, str(oid)):
        for tbl in ("trips", "people", "sites", "org_members"):
            await conn.execute(text("DELETE FROM " + tbl + " WHERE org_id=:o"), {"o": o})
        await conn.execute(text("DELETE FROM organizations WHERE id=:o"), {"o": o})
    await conn.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})


c.__exit__(None, None, None)
direct(_cleanup)
print("cleaned up")
print("\nlive spine: " + str(passed) + " passed, " + str(failed) + " failed")
raise SystemExit(1 if failed else 0)
