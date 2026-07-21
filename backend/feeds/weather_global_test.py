"""
Parser test for the Open-Meteo global weather feed. Run from repo root:
    python -m backend.feeds.weather_global_test
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

from backend.feeds import weather_global as W

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


PTS = [{"name": "Mumbai", "lat": 19.12, "lng": 72.90},
       {"name": "London", "lat": 51.51, "lng": -0.10}]


def block(rain, temp, wind, day="2026-07-20"):
    return {"daily": {"time": [day], "precipitation_sum": [rain],
                      "temperature_2m_max": [temp], "wind_gusts_10m_max": [wind]}}


# 1. a severe point emits, a calm point does not
out = W.parse_openmeteo([block(120, 30, 20), block(1, 18, 15)], PTS)
ok("only the severe point emits", len(out) == 1 and out[0]["geography"] == ["Mumbai"])
ok("source is open-meteo", out[0]["source"] == "open-meteo")
ok("very heavy rain ⇒ high importance", out[0]["importance"] == 84 and "rainfall" in out[0]["title"].lower())
ok("escalating status at high importance", out[0]["status"] == "escalating")
ok("carries office coordinates", out[0]["lat"] == 19.12 and out[0]["lng"] == 72.90)

# 2. worst-of when several thresholds trip — heat (82) beats high winds (55)
worst = W.parse_openmeteo([block(0, 46, 65)], PTS[:1])
ok("emits the single worst condition", len(worst) == 1 and worst[0]["importance"] == 82
   and "heat" in worst[0]["title"].lower())

# 3. sub-threshold weather is silent (no noise)
calm = W.parse_openmeteo([block(10, 35, 40)], PTS[:1])
ok("sub-threshold ⇒ no signal", calm == [])

# 4. single-object payload (one monitored point) is accepted like a list
single = W.parse_openmeteo(block(60, 20, 10), PTS[:1])
ok("single forecast object parsed", len(single) == 1 and single[0]["importance"] == 68)

# 5. external_id is stable per point+day (idempotent upsert key)
a = W.parse_openmeteo([block(120, 30, 20)], PTS[:1])[0]["external_id"]
b = W.parse_openmeteo([block(115, 31, 22)], PTS[:1])[0]["external_id"]
ok("external_id stable per point+day", a == b == "openmeteo-mumbai-2026-07-20")

# 6. missing daily arrays degrade quietly
ok("empty daily ⇒ no crash, no signal", W.parse_openmeteo([{"daily": {}}], PTS[:1]) == [])

print(f"\nweather_global: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
