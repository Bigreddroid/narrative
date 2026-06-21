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
from backend.feeds import launches
from backend.feeds import chokepoints
from backend.feeds import spaceweather
from backend.feeds import cyber
from backend.feeds import sanctions

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

print(f"\nfeeds: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
