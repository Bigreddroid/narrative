"""
Parity test for the server-side register audit. Run from repo root:
    python -m backend.services.registry_audit_test

These are the SAME scenarios as web/src/lib/registryAudit.test.mjs, case for case,
because the value of the port is that both copies reach the same verdict on the same
register. If either implementation drifts, one of the two suites goes red — which is
the only thing standing between us and a browser that says a register is clean while
the importer says it is broken (or, far worse, the reverse).

Pure: no DB, no network, no fixtures on disk.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

import re

from backend.services.registry_audit import CHECK_LABELS, audit_register

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


CC = {"India": "IN", "South Africa": "ZA", "United Arab Emirates": "AE"}


def site(**over):
    base = {"id": "s1", "name": "Site", "city": "City", "country": "India",
            "lat": 12.9, "lng": 77.6, "headcount": 100}
    base.update(over)
    return base


def has(r, check):
    return any(f["check"] == check for f in r["findings"])


def first(r, check):
    return next(f for f in r["findings"] if f["check"] == check)


# -- a clean register is reported clean ---------------------------------------
clean = audit_register([
    site(id="a", name="Alpha", city="Bengaluru"),
    site(id="b", name="Bravo", city="Pune", lat=18.5, lng=73.8),
], country_codes=CC)
ok("a clean register produces no findings", clean["clean"] is True and not clean["findings"])
ok("clean register still reports what it checked", clean["checked"] == 2)
ok("empty register is safe", audit_register([])["clean"] is True)

# -- THE observed failure: one identifier, two countries ----------------------
conflict = audit_register([
    site(id="AFR08", country="India", city="Johannesburg"),
    site(id="AFR08", country="South Africa", city="Johannesburg", lat=-26.1, lng=28.05),
], country_codes=CC)
ok("same identifier across two countries is caught", has(conflict, "conflicting_country"))
ok("conflicting country is critical", first(conflict, "conflicting_country")["severity"] == "critical")
ok("the finding names both countries", "India" in first(conflict, "conflicting_country")["detail"])
ok("it is NOT double-reported as a plain duplicate", not has(conflict, "duplicate_id"))

# A duplicate id within ONE country is a plain duplicate, not a country conflict.
dupe = audit_register([site(id="X1"), site(id="X1", lat=13.0)], country_codes=CC)
ok("duplicate identifier in one country is caught", has(dupe, "duplicate_id"))
ok("...and is not mislabelled a country conflict", not has(dupe, "conflicting_country"))

# -- missing / unmapped country -----------------------------------------------
no_country = audit_register([site(id="n1", country="")], country_codes=CC)
ok("a row with no country is caught", has(no_country, "missing_country"))
unmapped = audit_register([site(id="u1", country="Narnia")], country_codes=CC)
ok("a country with no ISO mapping is surfaced", has(unmapped, "unmapped_country"))
ok("unmapped country explains the consequence",
   re.search("holiday", unmapped["findings"][0]["detail"], re.I) is not None)
ok("a mapped country is not flagged",
   not has(audit_register([site(id="m1")], country_codes=CC), "unmapped_country"))

# -- coordinates ---------------------------------------------------------------
ok("missing coordinates are caught",
   has(audit_register([site(lat=None, lng=None)], country_codes=CC), "missing_coordinates"))
ok("out-of-range coordinates are caught",
   has(audit_register([site(lat=120, lng=12)], country_codes=CC), "invalid_coordinates"))
ok("0,0 is caught as an import default",
   has(audit_register([site(lat=0, lng=0)], country_codes=CC), "null_island"))
# Python-only hazard: bool is a subclass of int, so a stray True from a CSV parser
# would sail through a naive isinstance(v, int) check and become a latitude of 1.
ok("a boolean is not accepted as a coordinate",
   has(audit_register([site(lat=True, lng=True)], country_codes=CC), "missing_coordinates"))

# -- headcount -----------------------------------------------------------------
ok("a site with no headcount is flagged",
   has(audit_register([site(headcount=0)], country_codes=CC), "missing_headcount"))
ok("headcount finding explains the exposure consequence",
   re.search("exposure", first(audit_register([site(headcount=0)], country_codes=CC),
                               "missing_headcount")["detail"], re.I) is not None)

# -- geographic coherence ------------------------------------------------------
# Four Indian sites, one of which is actually in Johannesburg.
outlier = audit_register([
    site(id="i1", lat=12.9, lng=77.6), site(id="i2", lat=13.0, lng=77.5),
    site(id="i3", lat=18.5, lng=73.8), site(id="i4", lat=-26.2, lng=28.0),
], country_codes=CC)
ok("a site far from its country's other sites is flagged", has(outlier, "country_outlier"))
ok("the outlier is the wrong-country row", first(outlier, "country_outlier")["site_id"] == "i4")
ok("its peers are not flagged",
   len([f for f in outlier["findings"] if f["check"] == "country_outlier"]) == 1)
ok("too few peers => no outlier judgement",
   not has(audit_register([site(id="p1"), site(id="p2", lat=-26.2, lng=28.0)],
                          country_codes=CC), "country_outlier"))

# -- reporting shape -----------------------------------------------------------
mixed = audit_register([
    site(id="d1", country=""), site(id="d1", country="South Africa", lat=-26, lng=28),
    site(id="d2", headcount=0),
], country_codes=CC)
ok("findings are ranked critical-first", mixed["findings"][0]["severity"] == "critical")
ok("counts are broken down by check", len(mixed["by_check"]) >= 2)
ok("affected sites are counted distinctly", 1 <= mixed["affected_sites"] <= 3)
ok("every finding carries a human label", all(CHECK_LABELS.get(f["check"]) for f in mixed["findings"]))
ok("every finding names its row", all("site_id" in f for f in mixed["findings"]))
ok("every finding explains itself",
   all(isinstance(f["detail"], str) and len(f["detail"]) > 10 for f in mixed["findings"]))

print(f"\nregistry_audit: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
