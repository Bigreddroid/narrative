"""Property tests for feed parsers + synthesizer (pure). Run from repo root:
    python -m backend.feeds.feeds_test"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.feeds import synthesize as S
from backend.feeds import usgs
from backend.feeds import market
from backend.feeds import weather
from backend.feeds import gdacs
from backend.feeds import gdelt
from backend.feeds import gdelt_osint
from backend.feeds import launches
from backend.feeds import chokepoints
from backend.feeds import spaceweather
from backend.feeds import cyber
from backend.feeds import sanctions
from backend.feeds import osint_threatintel
from backend.feeds import rss_osint
from backend.services import osint_agent

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# ── synthesize ──────────────────────────────────────────────────────────────
ok("severity thresholds", S.severity_from(90) == "critical" and S.severity_from(65) == "high"
   and S.severity_from(45) == "medium" and S.severity_from(10) == "low")

m = S.synthesize({"title": "M7 quake", "category": "disaster", "importance": 90, "geography": ["Japan"], "source": "usgs"})
ok("direct impacts present", len(m["direct_impact"]) >= 1)
ok("disaster direct severity = critical", m["direct_impact"][0]["severity"] == "critical")
ok("indirect softer than direct", S.severity_from(90 - 25) != "critical")
ok("chain has 3 evidence-graded steps", len(m["consequence_chain"]) == 3)
ok("sources_analyzed carries feed", m["sources_analyzed"] == ["usgs"])
ok("affected_sectors populated", len(m["affected_sectors"]) >= 2)
ok("prediction_score in range", 20 <= m["prediction_score"] <= 95)
ok("prediction_reasoning is concrete", isinstance(m["prediction_reasoning"], str)
   and str(m["prediction_score"]) in m["prediction_reasoning"] and "Japan" in m["prediction_reasoning"])
ok("higher volatility ⇒ higher score",
   S.synthesize({"title": "war", "category": "conflict", "importance": 70})["prediction_score"]
   > S.synthesize({"title": "dry", "category": "drought", "importance": 70})["prediction_score"])

low = S.synthesize({"title": "minor", "category": "disaster", "importance": 30})
ok("low importance ⇒ low severity", low["direct_impact"][0]["severity"] == "low")
ok("unknown category falls back", S.synthesize({"title": "x", "category": "weird", "importance": 50})["direct_impact"][0]["sector"] == "Infrastructure")

# ── USGS earthquakes ────────────────────────────────────────────────────────
ok("importance: M4.5≈54", usgs.importance_from_magnitude(4.5) == 54)
ok("importance: M7≈84", usgs.importance_from_magnitude(7.0) == 84)
ok("importance clamps at 100", usgs.importance_from_magnitude(9.5) == 100)
ok("region parse", usgs._region("12km SSW of Ridgecrest, CA") == ["Ridgecrest", "CA"])

sample = {
    "features": [
        {"id": "us1", "properties": {"mag": 7.2, "place": "50km S of Town, Chile", "time": 1718000000000},
         "geometry": {"coordinates": [-71.5, -33.4, 25]}},
        {"id": "us2", "properties": {"mag": None, "place": "nowhere"}, "geometry": {"coordinates": [0, 0]}},  # skip
        {"id": "us3", "properties": {"mag": 5.0, "place": "Off coast of Japan", "time": 1718000001000},
         "geometry": {"coordinates": [142.0, 38.0, 10]}},
    ]
}
sig = usgs.parse_earthquakes(sample)
ok("skips magnitude-null feature", len(sig) == 2)
ok("signal has coords + category", sig[0]["lat"] == -33.4 and sig[0]["lng"] == -71.5 and sig[0]["category"] == "disaster")
ok("M7.2 ⇒ escalating + high importance", sig[0]["status"] == "escalating" and sig[0]["importance"] >= 80)
ok("external_id + source set", sig[0]["external_id"] == "us1" and sig[0]["source"] == "usgs")
ok("M5 ⇒ developing", sig[1]["status"] == "developing")

# synthesize works on a real parsed signal end-to-end
ok("parsed signal synthesizes", len(S.synthesize(sig[0])["direct_impact"]) >= 1)

# ── Weather: NWS alerts + NHC cyclones ──────────────────────────────────────
nws = {"features": [
    {"id": "nws1", "geometry": {"type": "Polygon", "coordinates": [[[-80.4, 25.6], [-80.0, 25.6], [-80.0, 26.0], [-80.4, 26.0]]]},
     "properties": {"id": "nws1", "severity": "Severe", "event": "Hurricane Warning",
                    "areaDesc": "Miami-Dade; Broward", "headline": "Hurricane Warning in effect"}},
    {"id": "nws2", "geometry": None, "properties": {"severity": "Extreme", "event": "No geometry"}},  # skip
]}
wa = weather.parse_nws_alerts(nws)
ok("nws skips geometry-less alert", len(wa) == 1)
ok("nws polygon centroid placed", abs(wa[0]["lng"] - (-80.2)) < 0.01 and abs(wa[0]["lat"] - 25.8) < 0.01)
ok("nws severe ⇒ importance 72 + escalating", wa[0]["importance"] == 72 and wa[0]["status"] == "escalating")
ok("nws category = storm", wa[0]["category"] == "storm" and wa[0]["source"] == "nws")

nhc = {"activeStorms": [
    {"id": "al01", "name": "Alberto", "classification": "HU", "intensity": "75", "movementDir": "NW",
     "latitudeNumeric": 25.3, "longitudeNumeric": -80.2, "tcType": "Atlantic"},
    {"id": "al02", "name": "NoCoords", "classification": "TS", "latitudeNumeric": None, "longitudeNumeric": None},  # skip
]}
ns = weather.parse_nhc_storms(nhc)
ok("nhc skips coordless storm", len(ns) == 1)
ok("nhc hurricane ⇒ importance 90 + escalating", ns[0]["importance"] == 90 and ns[0]["status"] == "escalating")
ok("nhc coords + category storm", ns[0]["lat"] == 25.3 and ns[0]["lng"] == -80.2 and ns[0]["category"] == "storm")
ok("storm signal synthesizes (SECTOR_MAP has storm)", S.synthesize(ns[0])["direct_impact"][0]["sector"] == "Shipping & Logistics")

# ── GDACS multi-hazard ──────────────────────────────────────────────────────
gd = {"features": [
    {"geometry": {"type": "Point", "coordinates": [120.5, 14.6]},
     "properties": {"eventtype": "TC", "eventid": 1000123, "name": "ALBERTO", "alertlevel": "Red", "country": "Philippines"}},
    {"geometry": {"type": "Point", "coordinates": [35.0, 38.0]},
     "properties": {"eventtype": "EQ", "eventid": 2000, "name": "M6.1", "alertlevel": "Orange", "country": "Turkey"}},
    {"geometry": {"type": "Point", "coordinates": [45.0, 5.0]},
     "properties": {"eventtype": "DR", "eventid": 3000, "name": "Horn drought", "alertlevel": "Green", "country": "Somalia"}},
    {"geometry": {"type": "Point", "coordinates": [14.0, 40.8]},
     "properties": {"eventtype": "VO", "eventid": 5000, "name": "Vesuvius", "alertlevel": "Orange", "country": "Italy"}},
    {"geometry": None, "properties": {"eventtype": "FL", "eventid": 4000}},  # skip
]}
gs = gdacs.parse_gdacs(gd)
ok("gdacs skips geometry-less event", len(gs) == 4)
ok("gdacs TC ⇒ storm + Red 90 escalating", gs[0]["category"] == "storm" and gs[0]["importance"] == 90 and gs[0]["status"] == "escalating")
ok("gdacs coords [lat,lng]", gs[0]["lat"] == 14.6 and gs[0]["lng"] == 120.5)
ok("gdacs EQ ⇒ disaster + Orange 72", gs[1]["category"] == "disaster" and gs[1]["importance"] == 72)
ok("gdacs DR ⇒ drought + Green 45 developing", gs[2]["category"] == "drought" and gs[2]["importance"] == 45 and gs[2]["status"] == "developing")
ok("gdacs external_id namespaced", gs[0]["external_id"] == "gdacs-TC1000123" and gs[0]["source"] == "gdacs")
ok("drought synthesizes ⇒ Agriculture direct", S.synthesize(gs[2])["direct_impact"][0]["sector"] == "Agriculture")
ok("volcano synthesizes ⇒ Aviation direct", S.synthesize(gs[3])["direct_impact"][0]["sector"] == "Aviation")

# ── GDELT geocoded activity ─────────────────────────────────────────────────
ok("gdelt importance scales w/ count", gdelt.importance_from_count(2) == 38 and gdelt.importance_from_count(20) == 65)
ok("gdelt importance caps at 95", gdelt.importance_from_count(40) == 95 and gdelt.importance_from_count(1000) == 95)
gj = {"features": [
    {"geometry": {"type": "Point", "coordinates": [44.4, 33.3]}, "properties": {"name": "Baghdad, Iraq", "count": 40}},
    {"geometry": {"type": "Point", "coordinates": [2.35, 48.85]}, "properties": {"name": "Paris, France", "count": 2}},
    {"geometry": None, "properties": {"name": "nowhere", "count": 5}},  # skip
]}
ge = gdelt.parse_gdelt(gj)
ok("gdelt skips geometry-less feature", len(ge) == 2)
ok("gdelt high count ⇒ 95 escalating conflict", ge[0]["importance"] == 95 and ge[0]["status"] == "escalating" and ge[0]["category"] == "conflict")
ok("gdelt coords [lat,lng]", ge[0]["lat"] == 33.3 and ge[0]["lng"] == 44.4)
ok("gdelt low count ⇒ developing", ge[1]["importance"] == 38 and ge[1]["status"] == "developing")
ok("gdelt external_id slugged", ge[0]["external_id"] == "gdelt-baghdad--iraq" and ge[0]["source"] == "gdelt")
ok("gdelt conflict synthesizes ⇒ Defense direct", S.synthesize(ge[0])["direct_impact"][0]["sector"] == "Defense")

# ── OSINT: GDELT DOC article parser (pure, raw candidates for triage) ─────────
gdoc = {"articles": [
    {"url": "https://bbc.com/a1", "title": "Major earthquake strikes Iran",
     "seendate": "20260625T074500Z", "domain": "bbc.com", "language": "English",
     "sourcecountry": "United Kingdom"},
    {"url": "https://bbc.com/a1", "title": "dup url dropped",                  # dup url → skipped
     "seendate": "20260625T074500Z", "domain": "bbc.com", "language": "English"},
    {"url": "https://x.fr/a2", "title": "Greve a Paris", "language": "French"},  # non-English → skipped
    {"url": "", "title": "no url", "language": "English"},                     # no url → skipped
    {"url": "https://y.com/a3", "title": "", "language": "English"},           # no title → skipped
]}
gd = gdelt_osint.parse_gdelt_doc(gdoc)
ok("gdelt-doc keeps only valid unique English articles", len(gd) == 1)
ok("gdelt-doc external_id namespaced + url-hashed",
   gd[0]["external_id"].startswith("gdelt-") and len(gd[0]["external_id"]) == 22)
ok("gdelt-doc puts domain in source-context field", gd[0]["subreddit"] == "bbc.com")
ok("gdelt-doc empty body (headline is the signal)",
   gd[0]["selftext"] == "" and gd[0]["title"].startswith("Major earthquake"))
ok("gdelt-doc seendate → epoch seconds",
   isinstance(gd[0]["created_utc"], float) and gd[0]["created_utc"] > 1_700_000_000)
ok("gdelt-doc empty payload ⇒ []", gdelt_osint.parse_gdelt_doc({}) == [])
# candidate flows through the SAME triage pipeline, tagged with the gdelt source
gd_sig = osint_agent._heuristic_triage(gd[0], source=gdelt_osint.SOURCE)[0]
ok("gdelt-doc candidate triages to disaster + osint_gdelt source",
   gd_sig and gd_sig["category"] == "disaster" and gd_sig["source"] == "osint_gdelt")
ok("gdelt-doc triaged signal synthesizes", len(S.synthesize(gd_sig)["direct_impact"]) >= 1)

# ── Launch Library 2 ────────────────────────────────────────────────────────
ll = {"results": [
    {"id": "abc-123", "name": "Falcon 9 | Starlink", "net": "2026-06-20T12:00:00Z",
     "launch_service_provider": {"name": "SpaceX"},
     "pad": {"name": "SLC-40", "latitude": "28.56", "longitude": "-80.57",
             "location": {"name": "Cape Canaveral, FL, USA"}}},
    {"id": "no-pad", "name": "Mystery", "pad": {"name": "?", "latitude": None, "longitude": None}},  # skip
]}
lr = launches.parse_launches(ll)
ok("launches skips pad-less entry", len(lr) == 1)
ok("launch coords parsed from strings", lr[0]["lat"] == 28.56 and lr[0]["lng"] == -80.57)
ok("launch ⇒ space category + importance", lr[0]["category"] == "space" and lr[0]["importance"] == 55)
ok("launch external_id + source", lr[0]["external_id"] == "ll2-abc-123" and lr[0]["source"] == "launchlibrary")
ok("launch synthesizes ⇒ Aerospace direct", S.synthesize(lr[0])["direct_impact"][0]["sector"] == "Aerospace")

# ── Chokepoint Congestion Index (derived from AIS) ──────────────────────────
ok("haversine ~111km per degree lng at equator", abs(chokepoints.haversine_km(0, 0, 0, 1) - 111.19) < 0.5)
ok("haversine zero distance", chokepoints.haversine_km(26.57, 56.25, 26.57, 56.25) == 0.0)
ok("congestion 0 at no vessels", chokepoints.congestion_from_count(0) == 0.0)
ok("congestion saturates ~0.63 at TAU", abs(chokepoints.congestion_from_count(40) - 0.6321) < 0.01)
ok("congestion monotonic", chokepoints.congestion_from_count(80) > chokepoints.congestion_from_count(40))

hormuz_ships = [{"lat": 26.57, "lng": 56.25} for _ in range(5)]
cc = chokepoints.chokepoint_congestion(hormuz_ships)
hormuz = next(c for c in cc if c["name"] == "Strait of Hormuz")
ok("vessels counted in Hormuz zone", hormuz["count"] == 5 and hormuz["congestion"] > 0)
ok("other chokepoints empty", sum(c["count"] for c in cc if c["name"] != "Strait of Hormuz") == 0)

st = chokepoints.sector_stress(cc)
ok("oil chokepoint raises Shipping AND Energy", "Shipping & Logistics" in st and "Energy" in st and st["Energy"] > 0)
ok("sector stress bounded [0,1]", all(0 <= v <= 1 for v in st.values()))

malacca_ships = [{"lat": 1.80, "lng": 102.50} for _ in range(3)]
st2 = chokepoints.sector_stress(chokepoints.chokepoint_congestion(malacca_ships))
ok("non-oil chokepoint raises Shipping only", "Shipping & Logistics" in st2 and "Energy" not in st2)
ok("no vessels ⇒ no stress", chokepoints.sector_stress(chokepoints.chokepoint_congestion([])) == {})

# ── NOAA SWPC space weather ─────────────────────────────────────────────────
kp_json = [["time_tag", "Kp", "a_running", "station_count"],
           ["2026-06-18 00:00:00", "3.00", "5", "8"],
           ["2026-06-18 03:00:00", "7.00", "9", "8"]]
ok("parse_kp takes latest row (legacy list-of-lists)", spaceweather.parse_kp(kp_json) == 7.0)
ok("parse_kp header-only ⇒ None", spaceweather.parse_kp([["time_tag", "Kp"]]) is None)
ok("parse_kp real dict shape (newest last)",
   spaceweather.parse_kp([{"time_tag": "a", "Kp": 3.33}, {"time_tag": "b", "Kp": 7.0}]) == 7.0)
ok("parse_kp empty ⇒ None", spaceweather.parse_kp([]) is None)
ok("kp<5 ⇒ G0", spaceweather.kp_to_gscale(3) == "G0")
ok("kp mapping G1..G5", spaceweather.kp_to_gscale(5) == "G1" and spaceweather.kp_to_gscale(9) == "G5")
ok("quiet kp ⇒ no stress", spaceweather.sector_stress(3) == {})
storm = spaceweather.sector_stress(9)
ok("G5 storm stresses all space sectors", set(storm) == set(spaceweather.SWPC_SECTORS))
ok("Aerospace most exposed + bounded", storm["Aerospace"] == 1.0 and all(0 <= v <= 1 for v in storm.values()))
ok("G3 partial stress", abs(spaceweather.sector_stress(7)["Aerospace"] - 0.6) < 1e-9)

# ── CISA KEV cyber (non-geo) ────────────────────────────────────────────────
kev = {"vulnerabilities": [
    {"cveID": "CVE-2026-1111", "vendorProject": "Acme", "product": "Router",
     "vulnerabilityName": "RCE", "shortDescription": "Remote code execution.",
     "dateAdded": "2026-06-10", "knownRansomwareCampaignUse": "Known"},
    {"cveID": "CVE-2026-2222", "vendorProject": "Globex", "product": "VPN",
     "shortDescription": "Auth bypass.", "dateAdded": "2026-06-15", "knownRansomwareCampaignUse": "Unknown"},
    {"vendorProject": "NoCVE", "dateAdded": "2026-06-18"},  # skip (no cveID)
]}
kv = cyber.parse_kev(kev)
ok("kev skips entry without cveID", len(kv) == 2)
ok("kev sorted newest dateAdded first", kv[0]["external_id"] == "CVE-2026-2222")
ok("kev ransomware ⇒ importance 80 escalating", kv[1]["importance"] == 80 and kv[1]["status"] == "escalating")
ok("kev non-ransomware ⇒ 60 developing", kv[0]["importance"] == 60 and kv[0]["status"] == "developing")
ok("kev is non-geo cyber signal", kv[0]["lat"] is None and kv[0]["category"] == "cyber" and kv[0]["source"] == "cisa")
ok("kev carries no geography (keeps vendors out of exposure regions)", kv[0]["geography"] == [])
ok("only ransomware-flagged clear the non-geo gate (importance ≥ 80)", [s for s in kv if s["importance"] >= 80] == [kv[1]])
ok("cyber synthesizes ⇒ Technology direct", S.synthesize(kv[0])["direct_impact"][0]["sector"] == "Technology")

# ── Sanctions (OpenSanctions, reference) ────────────────────────────────────
ents = [
    {"id": "ent-1", "schema": "Person", "caption": "John Target",
     "properties": {"country": ["ru"], "topics": ["sanction"]}, "datasets": ["us_ofac_sdn"]},
    {"id": "ent-2", "schema": "Company", "caption": "Shell Co",
     "properties": {"country": ["ir", "ae"], "topics": ["crime.fin"]}, "datasets": ["default"]},
    {"schema": "Person", "caption": "No ID"},  # skip
]
sr = sanctions.parse_targets(ents)
ok("sanctions skips id-less entity", len(sr) == 2)
ok("sanctions namespaced id + name", sr[0]["external_id"] == "opensanctions-ent-1" and sr[0]["name"] == "John Target")
ok("sanctions extracts countries", sr[0]["countries"] == ["ru"])
ok("sanctions topic flags sanctioned", sr[0]["sanctioned"] is True)
ok("sanction category synthesizes ⇒ Banking direct",
   S.synthesize({"category": "sanction", "importance": 60, "title": "x"})["direct_impact"][0]["sector"] == "Banking")

# ── Live-wiring accessors (cached vessels + Kp) ─────────────────────────────
import asyncio
from backend.api.routes import vessels as vroute

vroute._cache.clear()
vroute._cache["bbox1"] = (0.0, [{"mmsi": 1, "lat": 26.57, "lng": 56.25}, {"mmsi": 2, "lat": 0, "lng": 0}])
vroute._cache["bbox2"] = (0.0, [{"mmsi": 2, "lat": 0, "lng": 0}, {"mmsi": 3, "lat": 1, "lng": 1}])
cv = vroute.cached_vessels()
ok("cached_vessels dedups by mmsi across bboxes", len(cv) == 3)
vroute._cache.clear()
ok("cached_vessels empty when cache empty", vroute.cached_vessels() == [])

import time as _t
spaceweather._kp_cache["ts"] = _t.monotonic()
spaceweather._kp_cache["value"] = 6.0
ok("latest_kp serves fresh cache w/o network", asyncio.run(spaceweather.latest_kp()) == 6.0)
spaceweather._kp_cache["ts"] = 0.0
spaceweather._kp_cache["value"] = None

# ── Market layer ────────────────────────────────────────────────────────────
csv = "Symbol,Date,Time,Open,High,Low,Close,Volume,Name\nCB.F,2026-06-18,21:00:00,80.00,82,79,84.00,1000,Brent"
row = market.parse_stooq_csv(csv)
ok("stooq parse maps symbol→sector", row["symbol"] == "cb" and row["sector"] == "Energy" and row["label"] == "Brent Crude")
ok("stooq close + change%", row["price"] == 84.0 and row["change_pct"] == 5.0)
ok("stooq unknown symbol ⇒ None", market.parse_stooq_csv("Symbol,Open,Close\nXYZ.F,1,2") is None)

spx = market.parse_stooq_csv("Symbol,Date,Time,Open,High,Low,Close,Volume,Name\n^SPX,2026-06-18,21:00,5000,5100,4990,5050,0,SP500")
ok("equity index ⇒ Equities sector, ^ stripped", spx["symbol"] == "spx" and spx["sector"] == "Equities" and spx["change_pct"] == 1.0)
vix = market.parse_stooq_csv("Symbol,Date,Time,Open,High,Low,Close,Volume,Name\n^VIX,2026-06-18,21:00,15,20,14,18,0,VIX")
ok("VIX ⇒ Volatility sector", vix["symbol"] == "vix" and vix["sector"] == "Volatility" and vix["change_pct"] == 20.0)

fx = market.parse_frankfurter({"base": "USD", "rates": {"EUR": 0.92, "GBP": 0.79, "JPY": 157.0, "CNY": 7.2}})
ok("frankfurter ⇒ 4 FX rows", len(fx) == 4 and fx[0]["sector"] == "FX")
ok("FX symbol format", any(r["symbol"] == "usdeur" for r in fx))

stress = market.sector_stress([
    {"sector": "Energy", "change_pct": 5}, {"sector": "Energy", "change_pct": 1}, {"sector": "FX", "change_pct": 0.5},
])
ok("sector_stress in [0,1]", all(0 <= v <= 1 for v in stress.values()))
ok("bigger moves ⇒ more stress", stress["Energy"] > stress["FX"])

# ── OSINT triage fixture (a parsed OSINT candidate, reddit-shaped) ────────────
rp = [{"external_id": "reddit-abc1", "title": "M7 earthquake strikes Iran",
       "selftext": "Tsunami warning issued.", "url": "https://reddit.com/x",
       "score": 4200, "created_utc": 1718000000}]

# ── OSINT: triage agent heuristic + geocode (pure, no live LLM) ──────────────
quake_sig = osint_agent._heuristic_triage(rp[0])[0]
ok("heuristic categorizes quake ⇒ disaster", quake_sig and quake_sig["category"] == "disaster")
ok("heuristic geocodes Iran via centroid", quake_sig and quake_sig["lat"] is not None)
ok("heuristic sets source + confidence", quake_sig["source"] == "osint_reddit" and quake_sig["confidence"] == 0.3)
ok("heuristic Signal synthesizes (category in SECTOR_MAP)",
   len(S.synthesize(quake_sig)["direct_impact"]) >= 1)

noise = osint_agent._heuristic_triage({"external_id": "reddit-z", "title": "my opinion on politics",
                                       "selftext": "", "score": 5, "created_utc": 1718000000})[0]
ok("heuristic drops keyword-less noise", noise is None)

war_sig = osint_agent._heuristic_triage({"external_id": "reddit-w", "title": "Missile strike on Kyiv, Ukraine",
                                         "selftext": "", "score": 9000, "created_utc": 1718000000})[0]
ok("heuristic conflict ⇒ category conflict", war_sig["category"] == "conflict")
ok("heuristic constrains category to SECTOR_MAP", war_sig["category"] in osint_agent.ALLOWED_CATEGORIES)

ok("geocode known country ⇒ centroid", osint_agent.geocode("Ukraine")[0] is not None)
ok("geocode empty ⇒ (None, None)", osint_agent.geocode("") == (None, None))

# ── OSINT: triage-decision flywheel — every judgement is logged with a reason ──
# (allow_llm=False forces the heuristic path: pure, no LLM/network.)
kept_sig, kept_dec = osint_agent.triage_with_decision(
    {"external_id": "reddit-w2", "title": "Missile strike on Kyiv, Ukraine", "selftext": "",
     "score": 9000, "created_utc": 1718000000}, allow_llm=False, source="osint_gdelt")
ok("kept decision flags kept=True + reason", kept_sig and kept_dec["kept"] and kept_dec["reason"] == "heuristic_match")
ok("kept decision carries source/method/category",
   kept_dec["source"] == "osint_gdelt" and kept_dec["method"] == "heuristic" and kept_dec["category"] == "conflict")
drop_sig, drop_dec = osint_agent.triage_with_decision(
    {"external_id": "reddit-z2", "title": "my opinion on politics", "selftext": "",
     "score": 5, "created_utc": 1718000000}, allow_llm=False)
ok("dropped decision flags kept=False + no_keyword reason",
   drop_sig is None and not drop_dec["kept"] and drop_dec["reason"] == "no_keyword")
ok("dropped decision still records external_id + title", drop_dec["external_id"] == "reddit-z2" and drop_dec["title"])

# ── OSINT: LLM triage maps fields + respects confidence floor (mock LLM) ──────
from backend.services import llm as _llm


class _LLMRes:
    def __init__(self, text):
        self.text = text


_saved_complete = _llm.complete
try:
    _llm.complete = lambda system, user, max_tokens, json_mode=False: _LLMRes(
        '{"relevant": true, "category": "conflict", "title": "Strike on Kyiv",'
        ' "summary": "Missiles hit the capital.", "location_name": "Ukraine",'
        ' "importance": 82, "confidence": 0.9}')
    _llm_sig = osint_agent._llm_triage({"external_id": "reddit-l1", "title": "raw", "selftext": "",
                                        "subreddit": "worldnews", "created_utc": 1718000000})[0]
    ok("llm triage maps category", _llm_sig and _llm_sig["category"] == "conflict")
    ok("llm triage maps importance + escalating status",
       _llm_sig["importance"] == 82 and _llm_sig["status"] == "escalating")
    ok("llm triage geocodes location_name", _llm_sig["lat"] is not None)
    ok("llm triage carries confidence", _llm_sig["confidence"] == 0.9)

    _llm.complete = lambda system, user, max_tokens, json_mode=False: _LLMRes(
        '{"relevant": true, "category": "conflict", "importance": 50, "confidence": 0.2}')
    ok("llm triage drops below confidence floor (0.4)", osint_agent._llm_triage(
        {"external_id": "reddit-l2", "title": "rumor", "selftext": "", "subreddit": "x"})[0] is None)

    _llm.complete = lambda system, user, max_tokens, json_mode=False: _LLMRes('{"relevant": false}')
    ok("llm triage drops not-relevant", osint_agent._llm_triage(
        {"external_id": "reddit-l3", "title": "opinion", "selftext": "", "subreddit": "x"})[0] is None)
finally:
    _llm.complete = _saved_complete

# ── OSINT: threat-intel (ransomware.live) candidate parser ───────────────────
ti_raw = [
    {"victim": "Acme Mfg", "group": "safepay", "country": "DE", "activity": "Manufacturing",
     "attackdate": "2026-06-27T18:28:12.666586+00:00", "claim_url": "http://x.onion/acme",
     "description": "A maker of widgets."},
    {"victim": "Acme Mfg", "group": "safepay",  # dup (same group|victim|date) → skipped
     "attackdate": "2026-06-27T18:28:12.666586+00:00"},
    {"group": "play", "country": "US"},  # no victim → skipped
]
ti = osint_threatintel.parse_threatintel(ti_raw)
ok("threatintel keeps unique victims, skips dup + victimless", len(ti) == 1)
ok("threatintel external_id namespaced", ti[0]["external_id"].startswith("threatintel-"))
ok("threatintel title carries group + victim + ransomware keyword",
   "safepay" in ti[0]["title"] and "Acme Mfg" in ti[0]["title"] and "Ransomware" in ti[0]["title"])
ok("threatintel source-context set", ti[0]["subreddit"] == "ransomware.live")
ok("threatintel attackdate → epoch seconds",
   isinstance(ti[0]["created_utc"], float) and ti[0]["created_utc"] > 1_700_000_000)
ok("threatintel empty payload ⇒ []", osint_threatintel.parse_threatintel(None) == [])
# candidate flows through the SAME triage pipeline, tagged with the threatintel source
ti_sig = osint_agent._heuristic_triage(ti[0], source=osint_threatintel.SOURCE)[0]
ok("threatintel candidate triages to cyber + osint_threatintel source",
   ti_sig and ti_sig["category"] == "cyber" and ti_sig["source"] == "osint_threatintel")
ok("threatintel triaged signal synthesizes", len(S.synthesize(ti_sig)["direct_impact"]) >= 1)

# ── OSINT RSS/Atom v2 multi-source collector ─────────────────────────────────
_RSS_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
  <item><title>Missile strike hits Kyiv power grid</title>
    <link>https://ex.com/a</link>
    <description>An &lt;b&gt;airstrike&lt;/b&gt; hit the capital.</description>
    <pubDate>Wed, 10 Jun 2026 14:30:00 GMT</pubDate></item>
  <item><title>Dup link</title><link>https://ex.com/a</link></item>
  <item><link>https://ex.com/notitle</link></item>
</channel></rss>"""
rss = rss_osint.parse_rss(_RSS_XML, "news.google.com")
ok("rss keeps unique titled items, skips dup-link + titleless", len(rss) == 1)
ok("rss external_id namespaced + url-hashed",
   rss[0]["external_id"].startswith("rss-") and len(rss[0]["external_id"]) == 20)
ok("rss source label → subreddit context field", rss[0]["subreddit"] == "news.google.com")
ok("rss strips HTML from summary", "<b>" not in rss[0]["selftext"] and "airstrike" in rss[0]["selftext"])
ok("rss pubDate → epoch seconds", isinstance(rss[0]["created_utc"], float))

_ATOM_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>Earthquake M6 strikes coast</title>
    <link href="https://ex.com/self" rel="self"/>
    <link href="https://ex.com/atom1" rel="alternate"/>
    <summary>Magnitude 6 quake offshore</summary>
    <published>2026-06-10T14:30:00Z</published></entry>
</feed>"""
atom = rss_osint.parse_rss(_ATOM_XML, "reddit/worldnews")
ok("atom parses entry", len(atom) == 1)
ok("atom prefers rel=alternate over rel=self link", atom[0]["url"] == "https://ex.com/atom1")
ok("atom published → epoch seconds", isinstance(atom[0]["created_utc"], float))
ok("rss & atom date parsers agree on the same instant",
   rss_osint._parse_date("Wed, 10 Jun 2026 14:30:00 GMT") == rss_osint._parse_date("2026-06-10T14:30:00Z"))
ok("rss garbage XML ⇒ []", rss_osint.parse_rss("<not xml", "x") == [] and rss_osint.parse_rss("", "x") == [])
# RSS candidate flows through the SAME triage pipeline as the other OSINT sources
rss_sig = osint_agent._heuristic_triage(rss[0], source=rss_osint.SOURCE)[0]
ok("rss candidate triages to conflict + osint_rss source",
   rss_sig and rss_sig["category"] == "conflict" and rss_sig["source"] == "osint_rss")
ok("rss triaged signal synthesizes", len(S.synthesize(rss_sig)["direct_impact"]) >= 1)

# ── multi-INT: taxonomy.discipline_for (pure, deterministic) ──────────────────
from backend import taxonomy as TAX

ok("taxonomy has 13 categories + 7 disciplines",
   len(TAX.CATEGORIES) == 13 and len(TAX.DISCIPLINES) == 7)
ok("SECTOR_MAP keys == taxonomy.CATEGORIES", set(S.SECTOR_MAP) == set(TAX.CATEGORIES))

# source precedence, category fallback, both vocabularies, and the default.
_DISC_CASES = [
    ("usgs", "disaster", "MASINT"),          # source wins (MASINT feed)
    ("nhc", "storm", "MASINT"),
    ("cisa", "cyber", "CYBINT"),             # source wins
    ("osint_threatintel", "cyber", "CYBINT"),
    ("opensanctions", "sanction", "FININT"),
    ("osint_gdelt", "conflict", "HUMINT"),   # news source → category decides
    ("osint_rss", "market", "FININT"),
    (None, "technology", "CYBINT"),          # LLM-vocabulary category
    (None, "economy", "FININT"),
    (None, "climate", "MASINT"),
    (None, "geopolitics", "HUMINT"),
    (None, "cyber", "CYBINT"),               # feed-vocabulary category, no source
    (None, None, "HUMINT"),                  # default
    ("UNKNOWN_SRC", "totally_unknown_cat", "HUMINT"),  # graceful default
    ("CISA", "Cyber", "CYBINT"),             # case-insensitive
]
for src, cat, expected in _DISC_CASES:
    got = TAX.discipline_for(src, cat)
    ok(f"discipline_for({src!r},{cat!r}) == {expected}", got == expected)

ok("every discipline_for result is a valid discipline",
   all(TAX.discipline_for(s, c) in TAX.DISCIPLINES for s, c, _ in _DISC_CASES))

print(f"\nfeeds: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
