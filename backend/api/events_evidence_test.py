"""
Evidence-state classification for events (pure, stdlib only). Run from repo root:
    python -m backend.api.events_evidence_test

Guards the quarantine of severed events. The distinction being tested is the whole
point: an event with zero outlets is either fine (a structured feed publishes
records, not prose) or broken (an article-derived event that lost its articles).
Both used to render as a bare source_count of 0, so the deck could not tell a
USGS quake from 4,036 events orphaned by the cluster_worker outage.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.api.routes.events import _evidence_state

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


class E:
    def __init__(self, source):
        self.source = source


# Anything with outlets is sourced, whatever the feed.
ok("outlets present => sourced", _evidence_state(E("osint_rss"), 3) == "sourced")
ok("outlets present on structured feed => sourced", _evidence_state(E("nws"), 1) == "sourced")
ok("outlets present on null source => sourced", _evidence_state(E(None), 2) == "sourced")

# Structured feeds legitimately have no article — the agency IS the source.
for feed in ("nws", "usgs", "gdacs", "cisa", "launchlibrary", "open-meteo", "nhc", "imint"):
    ok(f"{feed} with no article => official_feed", _evidence_state(E(feed), 0) == "official_feed")
ok("demo seed with no article => official_feed",
   _evidence_state(E("wipro_demo_cyber"), 0) == "official_feed")

# Article-derived paths with no article are the DEFECT. The clusterer builds an
# event from an article and leaves source NULL, so NULL + zero outlets is severed.
ok("osint_rss with no article => severed", _evidence_state(E("osint_rss"), 0) == "severed")
ok("osint_gdelt with no article => severed", _evidence_state(E("osint_gdelt"), 0) == "severed")
ok("osint_mastodon with no article => severed", _evidence_state(E("osint_mastodon"), 0) == "severed")
ok("osint_threatintel with no article => severed", _evidence_state(E("osint_threatintel"), 0) == "severed")
ok("NULL source with no article => severed (clusterer path)",
   _evidence_state(E(None), 0) == "severed")
ok("empty-string source with no article => severed", _evidence_state(E(""), 0) == "severed")

# A structured feed added tomorrow must not be misread as broken. This is why the
# rule is "article-derived?" rather than an allowlist of known-good feeds.
ok("unknown new structured feed => official_feed, not severed",
   _evidence_state(E("copernicus_ems"), 0) == "official_feed")

print(f"\nevents_evidence: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
