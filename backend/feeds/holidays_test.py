"""
Parser + window test for the Nager.Date public-holidays feed. Run from repo root:
    python -m backend.feeds.holidays_test
"""

import sys
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

from backend.feeds import holidays as H

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# ── parse_holidays ────────────────────────────────────────────────────────────
raw = [
    {"date": "2026-01-26", "localName": "Gantantra Divas", "name": "Republic Day", "countryCode": "IN"},
    {"date": "2026-08-15", "localName": "Swatantrata Divas", "name": "Independence Day", "countryCode": "IN"},
    {"localName": "Undated", "name": "Undated"},  # no date ⇒ dropped
]
parsed = H.parse_holidays(raw)
ok("parses dated rows, drops undated", len(parsed) == 2)
ok("keeps English name", parsed[0]["name"] == "Republic Day")
ok("keeps local name", parsed[0]["localName"] == "Gantantra Divas")
ok("empty / None payload ⇒ []", H.parse_holidays(None) == [] and H.parse_holidays([]) == [])

# name falls back to localName when `name` missing
fb = H.parse_holidays([{"date": "2026-05-01", "localName": "Labour Day"}])
ok("name falls back to localName", fb[0]["name"] == "Labour Day")

# ── upcoming (date-window filter) ─────────────────────────────────────────────
TODAY = date(2026, 8, 1)
up = H.upcoming(parsed, within_days=45, today=TODAY)
ok("only holidays inside the window return", len(up) == 1 and up[0]["name"] == "Independence Day")
ok("stamps in_days", up[0]["in_days"] == 14)

# past holidays excluded, far-future excluded
future = [{"date": "2026-07-20", "name": "Past"}, {"date": "2026-12-25", "name": "Far"}]
ok("past + far-future excluded", H.upcoming(future, 45, TODAY) == [])

# a holiday today (in_days == 0) is included
ok("today counts as upcoming",
   len(H.upcoming([{"date": "2026-08-01", "name": "Now"}], 45, TODAY)) == 1)

# soonest-first ordering
multi = [{"date": "2026-09-01", "name": "Later"}, {"date": "2026-08-10", "name": "Sooner"}]
ordered = H.upcoming(multi, 60, TODAY)
ok("sorted soonest-first", [h["name"] for h in ordered] == ["Sooner", "Later"])

# bad date strings degrade quietly
ok("malformed date ⇒ no crash",
   H.upcoming([{"date": "not-a-date", "name": "Bad"}], 45, TODAY) == [])

print(f"\nholidays: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
