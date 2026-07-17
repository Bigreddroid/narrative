"""
Property test for NATO Admiralty source-reliability grading (Phase 2e). Run from repo root:
    python -m backend.services.source_reliability_test

Pure, deterministic grading — no DB, no LLM. These lock in the two behaviours the
phase promised: a grade that (1) reflects source provenance and (2) *rises* with
independent corroboration.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

from backend.services import source_reliability as SR

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


def letter(source, count=0, hist=None):
    return SR.grade(source, count, hist)["reliability"]["code"]


def digit(source, count=0, hist=None):
    return SR.grade(source, count, hist)["credibility"]["code"]


# ── Provenance drives the reliability letter ──────────────────────────────────
ok("primary sensor (usgs) is A", letter("usgs") == "A")
ok("primary sensor (aisstream) is A", letter("aisstream") == "A")
ok("agency (cisa) is B", letter("cisa") == "B")
ok("wire (reuters) is B", letter("reuters") == "B")
ok("open aggregator (osint_gdelt) is C", letter("osint_gdelt") == "C")
ok("uncurated rss (osint_rss) is D", letter("osint_rss") == "D")

g = SR.grade("who_is_this", 0)
ok("unknown source, no history → F (cannot be judged)", g["reliability"]["code"] == "F")
ok("unknown source, no corroboration → digit 6", g["credibility"]["code"] == 6)
ok("unknown source grades F6", g["grade"] == "F6")

# ── Corroboration drives the credibility digit — and it RISES with corroboration ──
d0, d1, d2, d3 = (digit("osint_gdelt", n) for n in (0, 1, 2, 3))
# Lower digit = stronger credibility; more corroboration must never weaken it.
ok("credibility strengthens monotonically with corroboration", d0 >= d1 >= d2 >= d3)
ok("3+ independent sources → 1 (confirmed)", d3 == 1)
ok("2 independent sources → 2 (probably true)", d2 == 2)
ok("1 independent source → 3 (possibly true)", d1 == 3)
ok("5 sources still confirmed", digit("osint_rss", 5) == 1)

# An A/B single source is "possibly true", not "doubtful"; a weak one is doubtful.
ok("reliable single source, no corroboration → 3", digit("usgs", 0) == 3)
ok("reliable wire, no corroboration → 3", digit("reuters", 0) == 3)
ok("weak single source, no corroboration → 4 (doubtful)", digit("osint_rss", 0) == 4)

# ── Track record nudges the letter (only with a large-enough sample) ───────────
strong = {"n": 40, "kept_rate": 0.85, "avg_confidence": 0.7}
weak = {"n": 40, "kept_rate": 0.1, "avg_confidence": 0.4}
tiny = {"n": 3, "kept_rate": 1.0, "avg_confidence": 0.9}
ok("strong track record promotes C → B", letter("osint_gdelt", 0, strong) == "B")
ok("weak track record demotes C → D", letter("osint_gdelt", 0, weak) == "D")
ok("small sample does not move the letter", letter("osint_gdelt", 0, tiny) == "C")
ok("unknown source with a track record is judged (D, not F)",
   letter("mystery_feed", 0, {"n": 20, "kept_rate": 0.5, "avg_confidence": 0.5}) == "D")

# ── Shape / determinism ───────────────────────────────────────────────────────
h = {"n": 12, "kept_rate": 0.6, "avg_confidence": 0.5}
a, b = SR.grade("osint_gdelt", 2, h), SR.grade("osint_gdelt", 2, h)
ok("grading is deterministic", a == b)
ok("grade string == letter + digit",
   a["grade"] == a["reliability"]["code"] + str(a["credibility"]["code"]))
ok("both axes carry human labels", bool(a["reliability"]["label"] and a["credibility"]["label"]))
ok("rationale is a non-empty audit trail", isinstance(a["rationale"], list) and bool(a["rationale"]))

print(f"\nsource_reliability: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
