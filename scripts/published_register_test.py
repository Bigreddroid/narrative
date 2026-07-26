"""
Integrity test for demo/wipro/sites.published-offices.csv — the 121 published Wipro
offices that seed an otherwise-empty register.

This file is DATA, which is exactly why it needs a test. Nothing else in the repo
fails when a row of it is wrong: the import accepts it, the deck renders it, and the
first symptom is a dot in the wrong country on a board someone is making a decision
against. The checks below are the promises its README makes, asserted:

  • unique name+city   — the import is idempotent on that pair (no external_id), so a
                         collision does not add a site, it QUIETLY MERGES two of them
  • usable coordinates — in range, never Null Island
  • mapped countries   — every country resolves via backend/countries.py, or that site
                         silently loses its public-holiday layer
  • empty headcount    — the deliberate gap. A "plausible" number here becomes a
                         fabricated exposure figure the moment it is imported
  • valid enums        — type/criticality must match the API's allowlists or the row
                         is rejected at import time, not here

Pure — no network, no DB.

Run:  python -m scripts.published_register_test
"""

import csv
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.api.routes.sites import CRITICALITIES, SITE_TYPES
from backend.countries import to_iso2
from backend.services.registry_audit import audit_register

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}")


CSV_PATH = Path(__file__).resolve().parent.parent / "demo" / "wipro" / "sites.published-offices.csv"
ok("register file exists", CSV_PATH.is_file())

with CSV_PATH.open(newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))

ok("121 published offices", len(rows) == 121)
ok("43 countries", len({r["country"] for r in rows}) == 43)

# ── the import key ────────────────────────────────────────────────────────────
# No external_id ⇒ the importer dedupes on name+city. A duplicate pair here is not a
# cosmetic defect: the second row overwrites the first and a site vanishes.
ok("no row carries an external_id", all(not r["external_id"].strip() for r in rows))
key = Counter((r["name"].strip().lower(), r["city"].strip().lower()) for r in rows)
dupes = [k for k, c in key.items() if c > 1]
ok(f"name+city is unique across all rows ({dupes[:3]})", not dupes)

# ── coordinates ───────────────────────────────────────────────────────────────
bad_range, null_island, missing = [], [], []
for r in rows:
    if not r["lat"].strip() or not r["lng"].strip():
        missing.append(r["name"])
        continue
    lat, lng = float(r["lat"]), float(r["lng"])
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        bad_range.append(r["name"])
    if lat == 0 and lng == 0:
        null_island.append(r["name"])
ok(f"every row has coordinates ({missing[:3]})", not missing)
ok(f"coordinates are in range ({bad_range[:3]})", not bad_range)
ok(f"nothing at Null Island ({null_island[:3]})", not null_island)

# Co-located sites sharing one locality centroid is INTENDED (SJP1/SJP2, KDC1/2/3),
# so identical coordinates are not a defect — but they must stay inside one city.
by_coord: dict[tuple[str, str], set[str]] = {}
for r in rows:
    by_coord.setdefault((r["lat"], r["lng"]), set()).add(r["city"])
straddling = {c: v for c, v in by_coord.items() if len(v) > 1}
ok(f"shared coordinates never straddle two cities ({list(straddling.values())[:2]})",
   not straddling)

# ── countries ─────────────────────────────────────────────────────────────────
unmapped = sorted({r["country"] for r in rows if not to_iso2(r["country"])})
ok(f"every country maps to an ISO code ({unmapped})", not unmapped)

# ── the deliberate gap ────────────────────────────────────────────────────────
# 🔴 If this ever fails, someone has filled in headcounts we do not have. That is not
# an improvement to the fixture, it is a fabricated input to exposure and duty-of-care.
ok("headcount is empty on every row — we do not know these",
   all(not r["headcount"].strip() for r in rows))

# ── enums the API will enforce at import time ─────────────────────────────────
bad_type = sorted({r["type"] for r in rows} - SITE_TYPES)
bad_crit = sorted({r["criticality"] for r in rows} - CRITICALITIES)
ok(f"every type is one the API accepts ({bad_type})", not bad_type)
ok(f"every criticality is one the API accepts ({bad_crit})", not bad_crit)
ok("exactly one tier-1 — the published corporate office",
   sum(1 for r in rows if r["criticality"] == "tier-1") == 1)

# ── ASCII ─────────────────────────────────────────────────────────────────────
# Deliberate: this file round-trips through Windows consoles, cp1252 test output and
# CSV export/re-import, and a mojibaked site name is a site nobody can search for.
non_ascii = [r["name"] for r in rows
             if any(ord(c) > 127 for c in "".join(v or "" for v in r.values()))]
ok(f"every cell is ASCII ({non_ascii[:3]})", not non_ascii)

# ── what the register audit will say about it ─────────────────────────────────
# The same audit that ships to the customer with GET /sites. Asserting its verdict
# here means the deck's caveats can never quietly change without this failing.
audit_rows = [{
    "id": str(i), "name": r["name"], "city": r["city"], "country": r["country"],
    "lat": float(r["lat"]), "lng": float(r["lng"]), "headcount": None,
} for i, r in enumerate(rows)]
codes = {c: to_iso2(c) for c in {r["country"] for r in audit_rows}}
audit = audit_register(audit_rows, country_codes=codes)

ok("audit finds zero critical defects", audit["critical"] == 0)
ok("audit's only finding is the missing headcount, on all 121 rows",
   audit["by_check"] == {"missing_headcount": 121})

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
