"""
Tests for title-based near-duplicate detection. Run from repo root:
    python -m backend.consequence_engine.title_dedup_test
"""

from backend.consequence_engine import title_dedup as td

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# The real GDELT cluster that motivated this: a dozen near-identical Iran headlines.
IRAN = [
    "US Strikes Iran After Drone Attack",
    "U.S. strikes Iran",
    "US strikes Iran",
    "U.S. conducts military strike against Iran following drone attack on U.S. ship",
    "The United States has launched a military strike against Iran in retaliation for a drone attack on a U.S. Navy ship",
]
IRAN_GEO = ["Iran", "Persian Gulf"]

# 1. normalization: stopwords out, "U.S." → us, light stemming
toks = td.normalize_tokens("U.S. strikes Iran after a drone attack")
ok("normalize keeps content words", {"us", "strike", "iran", "drone", "attack"} <= toks)
ok("normalize drops stopwords", "after" not in toks and "a" not in toks)

# 2. every Iran headline dedupes against every other
all_pairs = all(
    td.is_duplicate(IRAN[i], IRAN[j], IRAN_GEO, IRAN_GEO)
    for i in range(len(IRAN)) for j in range(len(IRAN)) if i != j
)
ok("all Iran headlines cluster together", all_pairs)

# 3. same shape, different place — not merged
ok("different country stays separate",
   not td.is_duplicate("US strikes Iran", "US strikes Iraq", ["Iran"], ["Iraq"]))

# 4. same place, different action — not merged
ok("strike vs sanction stays separate",
   not td.is_duplicate("US strikes Iran", "US sanctions Iran", ["Iran"], ["Iran"]))

# 5. wholly unrelated — not merged
ok("unrelated stories stay separate",
   not td.is_duplicate("M7.5 earthquake near Yumare, Venezuela",
                       "Flood Warning issued for Reno, KS", ["Venezuela"], ["Kansas"]))

# 6. moderate-similarity pair: geography decides
a, b = "Israel and Iran exchange missile strikes", "Iran fires missiles at Israel"
ok("shared geography merges moderate match",
   td.is_duplicate(a, b, ["Israel", "Iran"], ["Israel", "Iran"]))
ok("disjoint geography keeps moderate match apart",
   not td.is_duplicate(a, b, ["Israel"], ["Japan"]))

# 7. empties never match
ok("empty titles never duplicate",
   not td.is_duplicate("", "anything", [], []) and not td.is_duplicate(None, None, None, None))

# 8. exact-title matcher (for structured feeds): identical stories merge, distinct stay
ok("exact: GDACS double-title matches",
   td.same_story_exact("Earthquake — Earthquake in Venezuela", "Earthquake in Venezuela"))
ok("exact: distinct quakes stay separate",
   not td.same_story_exact("M4.6 earthquake — 50 km ESE of Palu, Indonesia",
                           "M4.5 earthquake — 125 km NE of Tobelo, Indonesia"))
ok("exact: distinct launches keep single-char identifiers",
   not td.same_story_exact("Launch — Falcon 9 Block 5 | SDA Tranche 1 Transport Layer A",
                           "Launch — Falcon 9 Block 5 | SDA Tranche 1 Transport Layer D"))
ok("exact: empties never match", not td.same_story_exact("", "") and not td.same_story_exact(None, "x"))

print(f"\ntitle_dedup: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
