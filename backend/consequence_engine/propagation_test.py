"""
Property test for the server-side CPE. Run from repo root:
    python -m backend.consequence_engine.propagation_test
Mirrors the JS harness (web/src/lib/propagation.test.mjs) to confirm parity.
"""

from datetime import datetime, timezone, timedelta

from backend.consequence_engine import propagation as P

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


NOW = datetime(2026, 6, 18, tzinfo=timezone.utc)
NOW_MS = NOW.timestamp() * 1000.0


def iso_ago(h):
    return (NOW - timedelta(hours=h)).isoformat()


def chain(*types):
    return [{"step": i, "type": t, "content": f"n{i}"} for i, t in enumerate(types)]


def mk(id, **o):
    return {
        "id": id,
        "category": o.get("category", "conflict"),
        "canonical_title": o.get("title", f"Event {id}"),
        "importance_score": o.get("importance", 80),
        "first_detected_at": o.get("at", iso_ago(2)),
        "geographic_relevance": o.get("geography", ["Red Sea"]),
        "consequence_map": {
            "consequence_chain": o.get("chain", chain("VERIFIED FACT", "INFERRED MECHANISM", "SPECULATIVE EFFECT")),
            "sources_analyzed": o.get("sources", ["s1", "s2", "s3", "s4"]),
            "disputed_points": o.get("disputed", []),
            "direct_impact": o.get("direct", [{"sector": "Shipping & Logistics", "severity": "critical"}]),
            "indirect_impact": o.get("indirect", [{"sector": "Consumer Prices", "severity": "medium"}]),
        },
    }


def sec(model, key):
    for s in model["sectors"]:
        if s["key"] == key:
            return s["score"]
    return 0


def cem(events, edges=None):
    return P.compute_exposure_model(events, edges or [], NOW_MS)


# 1. determinism
m1 = cem([mk("A"), mk("B", direct=[{"sector": "Shipping", "severity": "high"}])], [{"source": "A", "target": "B", "weight": 0.7}])
m2 = cem([mk("A"), mk("B", direct=[{"sector": "Shipping", "severity": "high"}])], [{"source": "A", "target": "B", "weight": 0.7}])
ok("deterministic", m1 == m2)

# 2. bounded
m = cem([mk("A", importance=100), mk("B", importance=95)], [{"source": "A", "target": "B", "weight": 1}])
allx = m["sectors"] + m["regions"]
ok("bounded [0,100]", all(0 <= x["score"] <= 100 for x in allx))
ok("integers", all(isinstance(x["score"], int) for x in allx))

# 3. attribution
m = cem([mk("A"), mk("B"), mk("C")])
top = m["sectors"][0]
ok("drivers exist", len(top["drivers"]) > 0)
ok("driver pct sum <= 100", sum(d["pct"] for d in top["drivers"]) <= 100)

# 4. importance monotonicity
ok("higher importance => more", sec(cem([mk("A", importance=95)]), "shipping") > sec(cem([mk("A", importance=50)]), "shipping"))

# 5. severity monotonicity
crit = sec(cem([mk("A", direct=[{"sector": "Energy", "severity": "critical"}])]), "energy")
med = sec(cem([mk("A", direct=[{"sector": "Energy", "severity": "medium"}])]), "energy")
ok("critical > medium", crit > med)

# 6. mitigating lowers exposure
base = [mk("A", direct=[{"sector": "Energy", "severity": "critical"}])]
agg = sec(cem(base + [mk("B", direct=[{"sector": "Energy", "severity": "critical"}])]), "energy")
mit = sec(cem(base + [mk("B", direct=[{"sector": "Energy", "severity": "critical", "direction": "mitigating"}])]), "energy")
ok("mitigating < aggravating", mit < agg)

# 7. entity resolution
m = cem([
    mk("A", direct=[{"sector": "Shipping & Logistics", "severity": "high"}], indirect=[]),
    mk("B", direct=[{"sector": "Shipping", "severity": "high"}], indirect=[]),
])
ok("alias collapse", len([s for s in m["sectors"] if s["key"] == "shipping"]) == 1)

# 8. temporal decay
ok("stale < fresh", sec(cem([mk("A", at=iso_ago(24 * 30))]), "shipping") < sec(cem([mk("A", at=iso_ago(1))]), "shipping"))

# 9. corroboration + disputes
ok("more sources => more", sec(cem([mk("A", sources=["1", "2", "3", "4", "5", "6"])]), "shipping") > sec(cem([mk("A", sources=["1"])]), "shipping"))
ok("disputes => less", sec(cem([mk("A", disputed=["x", "y"])]), "shipping") < sec(cem([mk("A", disputed=[])]), "shipping"))

# 10. directed vs undirected
A = mk("A", direct=[{"sector": "Energy", "severity": "critical"}], indirect=[])
B = mk("B", direct=[{"sector": "Banking", "severity": "low"}], indirect=[], importance=20)
di = sec(cem([A, B], [{"source": "A", "target": "B", "weight": 0.9, "directed": True}]), "banking")
un = sec(cem([A, B], [{"source": "A", "target": "B", "weight": 0.9}]), "banking")
ok("undirected >= directed", un >= di)
ok("directed still amplifies", di > 0)

# 11. profile exposure
model = cem([mk("A"), mk("B", direct=[{"sector": "Energy", "severity": "critical"}], geography=["Europe"])])
pe = P.profile_exposure({"sectors": ["Energy"], "regions": ["Europe"]}, model)
ok("profile bounded", 0 <= pe["score"] <= 100)
ok("unmatched => 0", P.profile_exposure({"sectors": ["Nonexistent"]}, model)["score"] == 0)

# 12. no secret params leaked in meta
ok("meta has version", model["meta"]["version"] == P.ENGINE_VERSION)
ok("meta hides LAMBDA/K", "LAMBDA" not in model["meta"] and "K" not in model["meta"])

# 13. per-event exposure heat
m13 = cem([mk("A", importance=95), mk("B", importance=40)])
ok("event_scores present", m13["event_scores"].get("A") is not None and m13["event_scores"].get("B") is not None)
ok("event_scores bounded", all(0 <= s <= 100 for s in m13["event_scores"].values()))
ok("higher-driving event hotter", m13["event_scores"]["A"] > m13["event_scores"]["B"])

# 14. traffic disruption feeds the CPE
ev = [mk("A", direct=[{"sector": "Energy", "severity": "low"}], indirect=[], geography=["Red Sea"])]
base = P.compute_exposure_model(ev, [], NOW_MS)
wt = P.compute_exposure_model(ev, [], NOW_MS, {"A": {"vessels": 200, "aircraft": 50}})
ok("no shipping without traffic", sec(base, "shipping") == 0)
ok("traffic raises shipping", sec(wt, "shipping") > 0)
ok("traffic raises aviation", sec(wt, "aviation") > 0)

# 15. market stress amplifies stressed sectors
ev_m = [mk("A", direct=[{"sector": "Energy", "severity": "medium"}], indirect=[])]
base_e = sec(P.compute_exposure_model(ev_m, [], NOW_MS), "energy")
boost_e = sec(P.compute_exposure_model(ev_m, [], NOW_MS, None, {"Energy": 0.9}), "energy")
ok("market stress raises stressed sector", boost_e > base_e)
mkt_only = P.compute_exposure_model([], [], NOW_MS, None, {"Commodities": 0.8})
ok("market-only sector appears", sec(mkt_only, "commodities") > 0)

# 16. combine_stress merges independent stress sources (max per sector, clamped)
cs = P.combine_stress({"Energy": 0.5}, {"Energy": 0.7, "Shipping & Logistics": 0.3}, {"Aerospace": 0.9})
ok("combine takes max per sector", cs["Energy"] == 0.7)
ok("combine unions distinct sectors", cs["Shipping & Logistics"] == 0.3 and cs["Aerospace"] == 0.9)
ok("combine clamps to [0,1]", P.combine_stress({"X": 5, "Y": -2}) == {"X": 1.0})
ok("combine ignores None + bad values", P.combine_stress(None, {"Z": "bad"}) == {})

# 17. combined chokepoint + space-weather stress amplifies their sectors via the CPE
ev_c = [mk("A", direct=[{"sector": "Energy", "severity": "low"}], indirect=[])]
combined = P.combine_stress({"Shipping & Logistics": 0.8}, {"Aerospace": 0.9})
mc = P.compute_exposure_model(ev_c, [], NOW_MS, None, combined)
ok("chokepoint stress surfaces Shipping", sec(mc, "shipping") > 0)
ok("space-weather stress surfaces Aerospace", sec(mc, "aerospace") > 0)

# 18. cross-feed corroboration boosts a corroborated event's exposure
ev_co = [mk("A", importance=40, direct=[{"sector": "Energy", "severity": "low"}], indirect=[])]
base_co = sec(P.compute_exposure_model(ev_co, [], NOW_MS), "energy")
boost_co = sec(P.compute_exposure_model(ev_co, [], NOW_MS, corroboration={"A": {"index": 1.0}}), "energy")
ok("corroboration boosts exposure", boost_co > base_co)
ok("no corroboration ⇒ unchanged", sec(P.compute_exposure_model(ev_co, [], NOW_MS, corroboration=None), "energy") == base_co)
ok("zero index ⇒ unchanged", sec(P.compute_exposure_model(ev_co, [], NOW_MS, corroboration={"A": {"index": 0.0}}), "energy") == base_co)

print(f"\nServer CPE v{P.ENGINE_VERSION}: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
