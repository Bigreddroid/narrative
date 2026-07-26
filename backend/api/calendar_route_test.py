"""
Contract test for GET /context/calendar. Pure — the Nager.Date fetch is stubbed, so
this runs with no network and no DB.

The recurrence guard here is a SILENT TRUNCATION. The endpoint capped the register's
countries at 20 and returned nothing to say it had done so, which was invisible while
the register was a 13-row demo and became a 23-country hole the day it was replaced
with the published office list. A country whose calendar was never fetched rendered
identically to a country with no holidays in the window — on a security calendar,
the more expensive of the two readings.

So: the cap may exist, but whatever it drops MUST come back in `omitted`.

Run:  python -m backend.api.calendar_route_test
"""

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

from backend.api.routes import context as C

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}")


# ── stub the upstream ─────────────────────────────────────────────────────────
# Every country returns one holiday except ZZ_EMPTY's stand-in, so `no_source_coverage`
# stays exercised alongside the cap.
FETCHED: list[str] = []
NO_DATA = {"IN", "AE", "SA", "QA", "OM", "BH"}   # the real Nager 204 set


async def _stub(code: str, year: int):
    FETCHED.append(code)
    if code in NO_DATA:
        return []
    # Far enough out to survive any `days` window used below.
    return [{"date": f"{year}-12-25", "name": "Stub Day", "localName": "Stub Day"}]


C._holidays_cached = _stub


def call(countries: str, days: int = 60):
    FETCHED.clear()
    return asyncio.run(C.get_calendar(user=None, countries=countries, days=days))


# ── the register's real country list ──────────────────────────────────────────
# The 43 countries of demo/wipro/sites.published-offices.csv, by name — the shape the
# browser actually sends, since the register stores "United Arab Emirates", not "AE".
REGISTER = [
    "India", "United Arab Emirates", "Saudi Arabia", "Qatar", "Oman", "Bahrain",
    "United Kingdom", "Ireland", "Netherlands", "Belgium", "Luxembourg", "France",
    "Germany", "Austria", "Switzerland", "Denmark", "Norway", "Sweden", "Finland",
    "Poland", "Hungary", "Romania", "Portugal", "Turkey", "United States", "Canada",
    "Mexico", "Brazil", "Costa Rica", "Australia", "Bangladesh", "China", "Indonesia",
    "Japan", "Malaysia", "Philippines", "Singapore", "Taiwan", "Thailand",
    "South Korea", "Nigeria", "South Africa", "Kenya",
]
ok("register fixture is the full published country set", len(REGISTER) == 43)

r = call(",".join(REGISTER))

ok("every register country resolves to an ISO code", r["unresolved"] == [])
ok("none of the 43 are dropped by the cap", r["omitted"] == [])
ok("all 43 calendars are returned", len(r["holidays"]) == 43)
ok("all 43 were actually fetched", len(set(FETCHED)) == 43)
ok("names map back to codes for the caller", r["codes"]["South Korea"] == "KR")
ok("source gaps still reported separately",
   set(r["no_source_coverage"]) == {"IN", "AE", "SA", "QA", "OM", "BH"})

# ── the cap, when it does bite, is reported ───────────────────────────────────
prev = C._MAX_CODES
C._MAX_CODES = 5
try:
    r2 = call(",".join(REGISTER))
    ok("cap limits what is fetched", len(r2["holidays"]) == 5)
    ok("cap does not silently discard the rest", len(r2["omitted"]) == 38)
    ok("omitted names the countries dropped, as ISO codes",
       "KR" in r2["omitted"] and "IN" not in r2["omitted"])
    ok("nothing past the cap was fetched", len(set(FETCHED)) == 5)
finally:
    C._MAX_CODES = prev

# ── duplicates and junk ───────────────────────────────────────────────────────
r3 = call("India,India,India,Wakanda,United States")
ok("a repeated country is fetched once", FETCHED.count("IN") == 1)
ok("unknown country is reported, not silently dropped", r3["unresolved"] == ["Wakanda"])
ok("unknown country does not block the known ones", "US" in r3["holidays"])

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
