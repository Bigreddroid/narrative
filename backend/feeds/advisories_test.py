"""
Parser test for the government advisory feeds. Run from repo root:
    python -m backend.feeds.advisories_test

Pure: the fixtures below are trimmed copies of the REAL shapes returned by
travel.state.gov's RSS and the GOV.UK content API, so the test exercises the parsing
without depending on two public services being up.

The assertions that matter most are the ones about what we DON'T do: the two
authorities' scales are never merged, no numeric equivalence is invented between
them, and nothing is stored that neither government wrote.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

from backend.feeds.advisories import (
    SOURCE_FCDO, SOURCE_STATE, fcdo_slug, parse_fcdo, parse_state_rss,
)

passed = failed = 0


def ok(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}  {str(extra)[:200]}")


STATE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Belgium - Level 2: Exercise Increased Caution</title>
    <link>https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/belgium-travel-advisory.html</link>
    <pubDate>Thu, 23 Jul 2026</pubDate>
    <description><![CDATA[<p><b>Advisory summary</b></p><p>Exercise increased caution in Belgium due to <b>crime</b>, <b>terrorism</b>, and <b>unrest</b>.</p>]]></description>
  </item>
  <item>
    <title>India - Level 2: Exercise Increased Caution</title>
    <link>https://travel.state.gov/india.html</link>
    <pubDate>Mon, 06 Jul 2026</pubDate>
    <description><![CDATA[<p>Do not travel to Jammu &amp; Kashmir.</p>]]></description>
  </item>
  <item>
    <title>Worldwide Caution</title>
    <link>https://travel.state.gov/worldwide.html</link>
    <pubDate>Fri, 01 May 2026</pubDate>
    <description><![CDATA[<p>Global advisory.</p>]]></description>
  </item>
</channel></rss>"""

items = parse_state_rss(STATE_XML)

ok("country advisories are parsed", len(items) == 2, len(items))
ok("a non-country item is skipped rather than filed under a country",
   all(i["country"] != "Worldwide Caution" for i in items), [i["country"] for i in items])
ok("the country is separated from the level", items[0]["country"] == "Belgium", items[0]["country"])
ok("the issuer's own level code is kept", items[0]["level_code"] == "L2", items[0]["level_code"])
ok("the issuer's own level label is kept verbatim",
   items[0]["level_label"] == "Exercise Increased Caution", items[0]["level_label"])
ok("the authority is recorded", items[0]["authority"] == SOURCE_STATE)
ok("the source URL is kept so a reader can check us",
   items[0]["url"].startswith("https://travel.state.gov/"), items[0]["url"])
ok("the publication date is parsed", items[0]["published_at"] is not None)
ok("the publication date is timezone-aware",
   items[0]["published_at"].tzinfo is not None)
ok("HTML tags are stripped from the summary",
   "<b>" not in items[0]["summary"] and "<p>" not in items[0]["summary"], items[0]["summary"])
ok("the summary keeps the government's words",
   "Exercise increased caution in Belgium" in items[0]["summary"], items[0]["summary"])
ok("HTML entities are unescaped, not left raw",
   "&amp;" not in items[1]["summary"] and "Jammu & Kashmir" in items[1]["summary"],
   items[1]["summary"])
ok("no numeric risk score is invented for a State advisory",
   not any(k in items[0] for k in ("score", "risk", "normalised_level", "rating")),
   sorted(items[0]))

# ── FCDO ─────────────────────────────────────────────────────────────────────
FCDO_DOC = {
    "title": "India travel advice",
    "base_path": "/foreign-travel-advice/india",
    "public_updated_at": "2026-07-09T14:54:18+01:00",
    "description": "FCDO travel advice for India.",
    "details": {
        "country": {"name": "India", "slug": "india"},
        "alert_status": ["avoid_all_travel_to_parts"],
        "change_description": "New information about entry requirements.",
        "parts": [
            {"slug": "warnings-and-insurance", "body": "<p>Still current at 09:00 today.</p>"},
            {"slug": "safety-and-security", "body": "<p>Terrorists are <b>very likely</b> to try.</p>"},
        ],
    },
}

f = parse_fcdo(FCDO_DOC)
ok("an FCDO document is parsed", f is not None)
ok("the country comes from the document, not the URL", f["country"] == "India", f["country"])
ok("the authority is recorded", f["authority"] == SOURCE_FCDO)
ok("FCDO's machine vocabulary is preserved unchanged",
   f["level_code"] == "avoid_all_travel_to_parts", f["level_code"])
ok("the level label is readable without being reinterpreted",
   f["level_label"] == "Avoid all travel to parts", f["level_label"])
ok("named parts are kept under the issuer's own slugs",
   set(f["sections"]) == {"warnings-and-insurance", "safety-and-security"}, sorted(f["sections"]))
ok("section bodies are plain text", "<p>" not in f["sections"]["safety-and-security"])
ok("the summary is what the FCDO says CHANGED",
   f["summary"] == "New information about entry requirements.", f["summary"])
ok("the URL points back at gov.uk",
   f["url"] == "https://www.gov.uk/foreign-travel-advice/india", f["url"])
ok("the publication date is parsed from ISO-8601", f["published_at"] is not None)

no_alert = parse_fcdo({**FCDO_DOC, "details": {**FCDO_DOC["details"], "alert_status": []}})
ok("no alert is stated in words, not left blank",
   no_alert["level_label"] == "No specific travel alert", no_alert["level_label"])
ok("no alert has its own code rather than an empty string",
   no_alert["level_code"] == "none", no_alert["level_code"])

# 🔴 The property this whole design rests on.
ok("the two authorities' level codes share no vocabulary — they are never merged",
   items[0]["level_code"] != f["level_code"]
   and not str(f["level_code"]).startswith("L"),
   (items[0]["level_code"], f["level_code"]))

ok("a malformed document is refused rather than half-stored", parse_fcdo({}) is None)
ok("a non-dict is refused", parse_fcdo(None) is None)
ok("an empty feed parses to nothing rather than raising", parse_state_rss("") == [])

# ── slugs ────────────────────────────────────────────────────────────────────
ok("a simple country slugs directly", fcdo_slug("India") == "india")
ok("spaces become hyphens", fcdo_slug("United Arab Emirates") == "united-arab-emirates")
ok("punctuation is dropped", fcdo_slug("Cote d'Ivoire") == "cote-d-ivoire", fcdo_slug("Cote d'Ivoire"))
ok("a leading article is dropped, as GOV.UK does",
   fcdo_slug("The Bahamas") == "bahamas", fcdo_slug("The Bahamas"))
ok("an empty country produces no slug", fcdo_slug("") == "")

print(f"\nadvisories: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
