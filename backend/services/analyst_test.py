"""Property tests for analyst pure helpers (no DB/LLM). Run from repo root:
    python -m backend.services.analyst_test
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from datetime import datetime, timezone, timedelta

from backend.services.analyst import _format_context, aggregate_country_risk

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# ── _format_context ──────────────────────────────────────────────────────────
events = [
    {"id": "e1", "title": "M7 quake off Chile", "summary": "Strong quake.", "category": "disaster",
     "status": "escalating", "importance": 90, "geography": ["Chile"]},
    {"id": "e2", "title": "Strait tension", "summary": "Naval buildup.", "category": "conflict",
     "status": "developing", "importance": 70, "geography": ["Taiwan", "China"]},
]
exposure = {"pressure": 88, "sectors": [{"key": "Shipping & Logistics", "score": 95}],
            "regions": [{"key": "Asia", "score": 80}]}
ctx = _format_context(events, exposure)
ok("context numbers events 1..N", "[1]" in ctx and "[2]" in ctx)
ok("context includes titles", "M7 quake off Chile" in ctx)
ok("context includes exposure pressure", "pressure 88" in ctx)
ok("context includes top sector", "Shipping & Logistics 95" in ctx)
ok("context handles no exposure", "EVENTS:" in _format_context(events, None))

# ── aggregate_country_risk ───────────────────────────────────────────────────
now = datetime(2026, 6, 23, tzinfo=timezone.utc)
rows = [
    {"geography": ["Chile"], "importance": 90, "last_updated_at": now},                    # fresh, high
    {"geography": ["Chile"], "importance": 50, "last_updated_at": now - timedelta(days=7)}, # 1 half-life
    {"geography": ["Taiwan", "China"], "importance": 70, "last_updated_at": now},
    {"geography": [], "importance": 100, "last_updated_at": now},                           # no country → ignored
    {"geography": ["Peru"], "importance": 0, "last_updated_at": None},                      # null ts → 0.5 decay
]
risk = aggregate_country_risk(rows, now=now)
by = {r["country"]: r for r in risk}
ok("ranked desc by risk", all(risk[i]["risk"] >= risk[i + 1]["risk"] for i in range(len(risk) - 1)))
ok("Chile aggregates two events", by["Chile"]["events"] == 2)
ok("Chile risk = 90 + 50*0.5 = 115", abs(by["Chile"]["risk"] - 115.0) < 0.01)
ok("multi-country event counts for both", by["Taiwan"]["events"] == 1 and by["China"]["events"] == 1)
ok("empty geography ignored", all(r["country"] for r in risk))
ok("zero-importance country has 0 risk", by["Peru"]["risk"] == 0.0)
ok("top= caps results", len(aggregate_country_risk(rows, now=now, top=1)) == 1)

print(f"\nanalyst: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
