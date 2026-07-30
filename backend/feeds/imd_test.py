"""
Parser test for the IMD / India official-warning feed. Run from repo root:
    python -m backend.feeds.imd_test

The payload shapes below are copied from LIVE documents fetched from WMO SWIC on
2026-07-29, not invented: a CWC river-flood alert (which carries coordinates in
altitude/ceiling) and an IMD-Bengaluru thunderstorm alert (which does not).
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

from backend.feeds import imd as I

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


SITES = [
    {"city": "Bengaluru", "lat": 12.95, "lng": 77.66},
    {"city": "Mumbai",    "lat": 19.12, "lng": 72.90},
    {"city": "Balod",     "lat": 20.73, "lng": 81.20},   # guards the substring trap
]

# Live CWC flood alert — coordinates smuggled into altitude/ceiling.
CWC_XML = """<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
<cap:identifier>IN-1785323780596016_5</cap:identifier><cap:sender>CWC</cap:sender>
<cap:info><cap:event>Flood</cap:event><cap:urgency>Future</cap:urgency>
<cap:severity>Moderate</cap:severity><cap:certainty>Possible</cap:certainty>
<cap:headline>River Kosi at Basua continues above normal flood situation.</cap:headline>
<cap:description>Flowing at 46.78 m, above its Warning Level of 46.75 m.</cap:description>
<cap:area><cap:areaDesc>Kosi, Basua, Supaul, Bihar</cap:areaDesc>
<cap:altitude>26.13</cap:altitude><cap:ceiling>86.58</cap:ceiling></cap:area>
</cap:info></cap:alert>"""

# Live IMD alert — altitude/ceiling are ZERO; it must be placed by district name.
IMD_XML = """<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
<cap:identifier>IN-99887766_1</cap:identifier><cap:sender>IMD-Bengaluru</cap:sender>
<cap:info><cap:event>Light Thunderstorm with surface wind</cap:event>
<cap:urgency>Immediate</cap:urgency><cap:severity>Severe</cap:severity>
<cap:certainty>Likely</cap:certainty>
<cap:headline>Thunderstorm with lightning very likely.</cap:headline>
<cap:area><cap:areaDesc>Ballari, Belagavi, Bengaluru, Chikkamagaluru districts of Karnataka</cap:areaDesc>
<cap:altitude>0</cap:altitude><cap:ceiling>0</cap:ceiling></cap:area>
</cap:info></cap:alert>"""

# ── CAP parsing is namespace-prefix agnostic ─────────────────────────────────
cwc = I.parse_cap(CWC_XML)
imd = I.parse_cap(IMD_XML)
ok("namespaced CAP parses", cwc is not None and imd is not None)
ok("sender read verbatim", cwc["sender"] == "CWC" and imd["sender"] == "IMD-Bengaluru")
ok("severity lowercased for lookup", imd["severity"] == "severe")
ok("non-alert input is None, not a crash", I.parse_cap("<html>nope</html>") is None)

# ── 🔴 the 0/0 trap: IMD alerts must NOT land in the Atlantic ────────────────
ok("CWC altitude/ceiling read as coordinates", I._coords_from_cap(cwc) == (26.13, 86.58))
ok("IMD 0/0 is rejected, not treated as a location", I._coords_from_cap(imd) is None)
ok("out-of-range values rejected",
   I._coords_from_cap({"altitude": "999", "ceiling": "5"}) is None)

# ── district matching places IMD alerts ──────────────────────────────────────
hits = I.sites_named_by(imd["area_desc"], SITES)
ok("alert naming Bengaluru attaches to the Bengaluru site",
   [s["city"] for s in hits] == ["Bengaluru"])
ok("a site the alert does not name is not attached",
   all(s["city"] != "Mumbai" for s in hits))
# "Balodabazar" must not match the site "Balod" — whole-word matching, not substring.
ok("substring districts do not false-match a site",
   I.sites_named_by("Balodabazar, Bemetara districts", SITES) == [])
ok("alias resolves the register's spelling to IMD's district",
   len(I.sites_named_by("Bangalore Urban district", SITES)) == 1)

# ── signals ──────────────────────────────────────────────────────────────────
sig = I.to_signal(imd, SITES)
ok("one signal per covered site", len(sig) == 1)
ok("placed on the SITE's coordinates", sig[0]["lat"] == 12.95 and sig[0]["lng"] == 77.66)
ok("severe + immediate outranks severe alone", sig[0]["importance"] == 72 + 8)
ok("high importance ⇒ escalating", sig[0]["status"] == "escalating")
ok("IMD grades through the 'imd' source string", sig[0]["source"] == "imd")
ok("the issuer is named in the summary, not hidden", "IMD-Bengaluru" in sig[0]["summary"])
ok("the issuer's own headline is preserved verbatim",
   "Thunderstorm with lightning very likely." in sig[0]["summary"])

flood = I.to_signal(cwc, SITES)
ok("an alert naming no registered site falls back to its own coordinate",
   len(flood) == 1 and flood[0]["lat"] == 26.13)
ok("CWC is NOT relabelled as IMD", flood[0]["source"] == "gov_in_cwc")

# 🔴 An alert that names no site and carries no coordinate must be DROPPED, never
# placed at a country centroid — a warning shown over a site it does not cover is
# worse than one not shown.
nowhere = dict(imd, area_desc="Kupwara district of Jammu")
ok("unplaceable alert is dropped, not parked somewhere convenient",
   I.to_signal(nowhere, SITES) == [])

ok("external_id is stable per alert+place",
   I.to_signal(imd, SITES)[0]["external_id"] == sig[0]["external_id"])

# ── index filtering ──────────────────────────────────────────────────────────
idx = I.parse_wmo_index({"items": [
    {"id": "IN-1_1", "url": "in-ndma-xx/a.xml", "event": "Flood"},
    {"id": "AT-9_2", "url": "at/b.xml", "event": "Wind"},
    {"id": "IN-2_1"},                       # no url — unusable
    "not-a-dict",
]})
ok("only India's alerts with a document are indexed",
   [i["id"] for i in idx] == ["IN-1_1"])
ok("empty payload degrades quietly", I.parse_wmo_index({}) == [])

# ── the India handover must FAIL SAFE ────────────────────────────────────────
# weather_global drops Indian metros only while IMD is genuinely answering. A cold
# process has never heard from IMD, so India must still be on the model forecast —
# otherwise 27 of 121 sites are watched by nothing while the deck says "of 121".
I._last_answered_at = None
ok("cold start ⇒ India is NOT handed over to IMD", I.covers_india_now() is False)
I._mark_answered()
ok("after a successful fetch ⇒ IMD covers India", I.covers_india_now() is True)
import time as _time  # noqa: E402
I._last_answered_at = _time.monotonic() - (I.COVERAGE_TTL_SECONDS + 1)
ok("a stale success expires, handing India back to Open-Meteo",
   I.covers_india_now() is False)
I._last_answered_at = None

print(f"\nimd: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
