"""
Property test for cross-feed corroboration. Run from repo root:
    python -m backend.consequence_engine.corroboration_test
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

from backend.consequence_engine import corroboration as C

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


T = 1_000_000_000_000  # base epoch ms
H = 3600_000           # one hour in ms


def mk(id, source, lat, lng, ts=T):
    return {"id": id, "source": source, "lat": lat, "lng": lng, "ts": ts}


# 1. independent feeds at same place+time corroborate each other
two = [mk("a", "usgs", 0, 0), mk("b", "gdacs", 1, 1)]  # ~157 km apart, same time
r = C.corroborate(two)
ok("both events corroborated", r["a"]["count"] == 1 and r["b"]["count"] == 1)
ok("attribution names the other source", r["a"]["sources"] == ["gdacs"] and r["b"]["sources"] == ["usgs"])
ok("index in (0,1)", 0 < r["a"]["index"] < 1)

# 2. same source is NOT independent corroboration
same = C.corroborate([mk("a", "usgs", 0, 0), mk("b", "usgs", 1, 1)])
ok("same-source ⇒ no corroboration", same["a"]["count"] == 0 and same["a"]["index"] == 0.0)

# 3. spatial gate — far apart does not corroborate
far = C.corroborate([mk("a", "usgs", 0, 0), mk("b", "gdacs", 50, 50)])  # ~7300 km
ok("far apart ⇒ no corroboration", far["a"]["count"] == 0)

# 4. temporal gate — outside the window does not corroborate
late = C.corroborate([mk("a", "usgs", 0, 0), mk("b", "gdacs", 1, 1, T + 100 * H)])
ok("outside time window ⇒ no corroboration", late["a"]["count"] == 0)

# 5. non-geo events cannot be geo-corroborated
nong = C.corroborate([mk("a", "cisa", None, None), mk("b", "gdacs", 0, 0)])
ok("non-geo event ⇒ index 0", nong["a"]["index"] == 0.0 and nong["a"]["count"] == 0)

# 6. more distinct sources ⇒ higher index (monotonic)
cluster = [mk("t", "usgs", 0, 0), mk("c1", "gdacs", 0.5, 0.5), mk("c2", "gdelt", 0.5, -0.5)]
rc = C.corroborate(cluster)
ok("two distinct sources counted", rc["t"]["count"] == 2 and rc["t"]["sources"] == ["gdacs", "gdelt"])
ok("more sources ⇒ higher index", rc["t"]["index"] > r["a"]["index"])

# 7. duplicate source within range counts once
dup = C.corroborate([mk("t", "usgs", 0, 0), mk("c1", "gdacs", 0.4, 0.4), mk("c2", "gdacs", 0.3, 0.3)])
ok("repeated source deduped", dup["t"]["count"] == 1)

# 8. determinism
ok("deterministic", C.corroborate(cluster) == rc)

# 9. boost is bounded and monotone
ok("zero index ⇒ unchanged importance", C.corroboration_boost(80, 0) == 80.0)
ok("full index ⇒ +CORROB_W", C.corroboration_boost(100, 1.0) == 140.0)
ok("boost monotone in index", C.corroboration_boost(100, 0.5) > C.corroboration_boost(100, 0.1))

# 10. multi-INT cross-discipline uplift (XDISC_W) — default no-op, opt-in effect
def mkd(id, source, disc, lat, lng, ts=T):
    return {"id": id, "source": source, "discipline": disc, "lat": lat, "lng": lng, "ts": ts}

# disciplines are surfaced even at the default weight
tri_x = [mkd("t", "usgs", "MASINT", 0, 0), mkd("c1", "gdacs", "HUMINT", 0.4, 0.4),
         mkd("c2", "gdelt", "FININT", 0.3, -0.3)]
rx = C.corroborate(tri_x)
ok("disciplines surfaced (self + corroborators)",
   rx["t"]["disciplines"] == ["FININT", "HUMINT", "MASINT"])

# parity: at XDISC_W=0 the index equals the discipline-free index for the same geometry
tri_plain = [mk("t", "usgs", 0, 0), mk("c1", "gdacs", 0.4, 0.4), mk("c2", "gdelt", 0.3, -0.3)]
assert C.XDISC_W == 0.0, "XDISC_W must default to 0 (no-op) so existing behaviour is preserved"
ok("XDISC_W=0 ⇒ index unchanged vs discipline-free",
   rx["t"]["index"] == C.corroborate(tri_plain)["t"]["index"])

# effect: with the weight on, 3 DISTINCT disciplines score strictly higher than
# 3 sources all in ONE discipline (same geometry/source-count).
same_disc = [mkd("t", "usgs", "MASINT", 0, 0), mkd("c1", "gdacs", "MASINT", 0.4, 0.4),
             mkd("c2", "gdelt", "MASINT", 0.3, -0.3)]
_saved = C.XDISC_W
try:
    C.XDISC_W = 0.5
    hi = C.corroborate(tri_x)["t"]["index"]      # 3 disciplines
    lo = C.corroborate(same_disc)["t"]["index"]  # 1 discipline
    ok("cross-discipline convergence > single-discipline echo", hi > lo)
    ok("single-discipline uplift is a no-op (n_disc=1)",
       lo == C.corroborate(tri_plain)["t"]["index"])
finally:
    C.XDISC_W = _saved
ok("XDISC_W restored to default after test", C.XDISC_W == 0.0)

print(f"\ncorroboration: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
