"""
Property test for NATO Admiralty source-reliability grading (Phase 2e). Run from repo root:
    python -m backend.services.source_reliability_test

Pure, deterministic grading — no DB, no LLM. These lock in the two behaviours the
phase promised: a grade that (1) reflects source provenance and (2) *rises* with
independent corroboration.
"""

import asyncio
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

# ── The weather layer was entirely ungraded ───────────────────────────────────
# Measured before this was fixed: nws, nhc AND open-meteo every one graded F6,
# "cannot be judged". Matching is by substring and none of those strings contain
# "noaa", so the whole layer fell through the prior to unknown-source. These
# assertions exist so a future edit to the needle list cannot silently undo it.
ok("NWS alerts grade as an agency, not as unknown", letter("nws") == "A")
ok("NHC hurricanes grade as an agency, not as unknown", letter("nhc") == "A")
ok("IMD is a national met agency issuing warnings → A", letter("imd") == "A")
# A model forecast is NOT an issued warning, and must not borrow an agency's letter.
ok("open-meteo is a model aggregator, graded C not A", letter("open-meteo") == "C")
ok("an issued warning outranks a computed forecast",
   SR.RELIABILITY_CODES.index(letter("imd")) < SR.RELIABILITY_CODES.index(letter("open-meteo")))

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

# ── The convergence rationale must not borrow the two-source gate's vocabulary ──
# `corroboration_count` counts OTHER events nearby from different feeds; the gate counts
# distinct OUTLETS on THIS event. They legitimately disagree, so the drawer once showed
# "2 independent sources converged" above "1 outlet - did not meet the two-source bar".
# Saying "feeds ... nearby" instead of "sources" is what keeps the two readable apart, so
# lock it: a future edit that reintroduces "source" here silently recreates that
# contradiction on the one surface whose entire pitch is auditable sourcing.
_rationales = [
    " ".join(SR.grade(_src, _n)["rationale"]).lower()
    for _n in (0, 1, 2, 3, 5)
    for _src in ("usgs", "reuters", "osint_gdelt", "osint_rss", "who_is_this")
]
ok("no rationale calls nearby convergence a 'source' (25 source/count combinations)",
   not any("sources converged" in w or "source corroborated" in w for w in _rationales))
ok("convergence rationales name the measure they actually use ('feeds ... nearby')",
   all("feeds reported related activity nearby" in " ".join(SR.grade(s, n)["rationale"])
       for s in ("usgs", "osint_rss") for n in (2, 3)))

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

# ── attach_grades: the shared in-place grader for both corroboration surfaces ──
# No DB: source_history_map is stubbed to "no track record for anyone", so grades
# come from provenance + corroboration count alone (the deterministic core above).
_real_history = SR.source_history_map


async def _no_history(_db, _sources):
    return {}


SR.source_history_map = _no_history
try:
    # A usgs event (A) with 2 corroborators and an osint_rss event (D) with none.
    corrob = {"e1": {"count": 2, "disciplines": ["OSINT", "SIGINT"]}, "e2": {"count": 0}}
    events = [
        {"id": "e1", "source": "usgs", "discipline": "OSINT"},
        {"id": "e2", "source": "osint_rss", "discipline": "HUMINT"},
    ]
    asyncio.run(SR.attach_grades(None, corrob, events))
    ok("attach_grades grades the corroborated entry", corrob["e1"]["reliability"]["grade"] == "A2")
    ok("attach_grades carries the discipline through", corrob["e1"]["discipline"] == "OSINT")
    ok("digit reflects THIS entry's corroboration count",
       corrob["e1"]["reliability"]["credibility"]["code"] == 2)
    ok("uncorroborated weak source grades D4", corrob["e2"]["reliability"]["grade"] == "D4")

    # An entry with no matching event must still get a grade (F, cannot be judged),
    # never a KeyError — the UI renders every entry it's handed.
    orphan = {"ghost": {"count": 1}}
    asyncio.run(SR.attach_grades(None, orphan, events))
    ok("orphan corroboration entry grades on a null source, not a crash",
       orphan["ghost"]["reliability"]["reliability"]["code"] == "F")

    # Empty map is a no-op (and never queries history).
    empty = {}
    asyncio.run(SR.attach_grades(None, empty, events))
    ok("empty corroboration is a safe no-op", empty == {})
finally:
    SR.source_history_map = _real_history

print(f"\nsource_reliability: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
