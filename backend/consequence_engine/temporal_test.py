"""Property test for temporal. Run:  python -m backend.consequence_engine.temporal_test"""

from backend.consequence_engine import temporal as T

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


ok("ema constant", abs(T.ema([5, 5, 5]) - 5) < 1e-9)
ok("rising momentum > 0", T.momentum([10, 20, 30, 40, 60]) > 0)
ok("falling momentum < 0", T.momentum([60, 50, 40, 30, 10]) < 0)
ok("trend rising", T.trend_label(10) == "rising")
ok("trend falling", T.trend_label(-10) == "falling")
ok("trend stable", T.trend_label(0) == "stable")

target = {"id": "T", "category": "conflict", "geography": ["Red Sea", "Yemen"], "affected_sectors": ["Shipping & Logistics"]}
history = [
    {"id": "H1", "category": "conflict", "geography": ["Red Sea", "Suez"], "sectors": ["Shipping & Logistics"], "outcome": "materialized"},
    {"id": "H2", "category": "economics", "geography": ["United States"], "sectors": ["Banking"], "outcome": "failed"},
    {"id": "T", "category": "conflict", "geography": ["Red Sea"], "sectors": []},
]
analogs = T.find_analogs(target, history, 3)
ok("analogs exclude self", all(a["event"]["id"] != "T" for a in analogs))
ok("most similar first", analogs[0]["event"]["id"] == "H1")
ok("analog carries outcome", analogs[0]["event"]["outcome"] == "materialized")

evs = [
    {"id": "A", "first_detected_at": "2026-01-01T00:00:00+00:00"},
    {"id": "B", "first_detected_at": "2026-01-11T00:00:00+00:00"},
    {"id": "C", "first_detected_at": "2026-01-05T00:00:00+00:00"},
]
edges = [{"source": "A", "target": "B"}, {"source": "A", "target": "C"}]
ok("lead_lag median days", T.lead_lag(evs, edges) == 7)
ok("lead_lag null w/o timestamps", T.lead_lag([{"id": "A"}, {"id": "B"}], [{"source": "A", "target": "B"}]) is None)

print(f"\ntemporal: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
