"""
Property test for IMINT → event composition (Phase 2f). Run from repo root:
    python -m backend.services.imint_event_test

Pure function, no I/O: build_signal() takes an already-computed IMINT interpretation
and geolocation and decides whether the pair earns a real event on the graph/globe.
The point of these tests is the honesty gate — an interpretation we cannot place, or
can only place on a guess, must NOT become a pin.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

from backend import taxonomy
from backend.services import imint_event as E

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


def interp(assessment="Forward arming and refueling point", confidence=0.7, available=True):
    return {
        "available": available,
        "discipline": "IMINT",
        "trace": {"observe": ["two revetments"], "orient": [], "decide": []},
        "best": {
            "assessment": assessment,
            "confidence": confidence,
            "why": "revetments + fuel bladders",
            "facility_type": "FARP",
            "activity": "aircraft parked",
        },
    }


def loc(lat=50.45, lng=30.52, place="Kyiv", country="Ukraine", confidence=0.6, available=True):
    return {
        "available": available,
        "trace": {"observe": [], "orient": [], "decide": []},
        "best": {"lat": lat, "lng": lng, "place": place, "country": country,
                 "confidence": confidence, "why": "cyrillic signage"},
    }


SHA = "a" * 64

# ── The honesty gate: no interpretation, or no place, means no pin ───────────────
r = E.build_signal(interp(available=False), loc(), SHA)
ok("unavailable interpretation → no event", r["ok"] is False)
ok("unavailable interpretation → reason names the interpretation", "interpret" in r["reason"].lower())

r = E.build_signal(interp(), loc(available=False), SHA)
ok("unplaceable image → no event", r["ok"] is False)
ok("unplaceable image → reason names the location", "locat" in r["reason"].lower())

r = E.build_signal(interp(), loc(lat=None, lng=None), SHA)
ok("missing coordinates → no event", r["ok"] is False)

r = E.build_signal(interp(), loc(confidence=0.05), SHA)
ok("low-confidence location → no event (never pin a guess)", r["ok"] is False)
ok("low-confidence reason names confidence", "confiden" in r["reason"].lower())

r = E.build_signal(interp(), loc(lat=91.0), SHA)
ok("out-of-range latitude → no event", r["ok"] is False)

r = E.build_signal(interp(assessment=""), loc(), SHA)
ok("empty assessment → no event", r["ok"] is False)

# ── A well-evidenced pair earns a real, correctly-tagged event ──────────────────
r = E.build_signal(interp(), loc(), SHA)
ok("well-evidenced pair → event", r["ok"] is True)

s = r["signal"]
ok("event carries the interpreted coordinates", s["lat"] == 50.45 and s["lng"] == 30.52)
ok("event is sourced to imint", s["source"] == "imint")
ok("re-uploading the same image dedupes on its hash", s["external_id"] == SHA)
ok("title carries the assessment", "Forward arming" in s["title"])
ok("title carries the place", "Kyiv" in s["title"])
ok("summary carries the visual rationale", "revetments" in s["summary"])
ok("summary carries the facility type", "FARP" in s["summary"])
ok("geography carries the country", "Ukraine" in s["geography"])
ok("status is a valid event status", s["status"] in ("developing", "escalating", "resolved"))

# The whole point: this event must read as IMINT through the SAME deterministic
# taxonomy every other event goes through — not a hand-set string.
ok("event resolves to IMINT via the real taxonomy",
   taxonomy.discipline_for(s["source"], s["category"]) == taxonomy.IMINT)

# ── Importance is evidence-weighted and honestly capped ─────────────────────────
ok("importance is on the 0-100 scale", 0 <= s["importance"] <= 100)
ok("a single photo never outranks a major hazard",
   s["importance"] <= E.IMPORTANCE_CEILING and E.IMPORTANCE_CEILING <= 80)

strong = E.build_signal(interp(confidence=0.95), loc(confidence=0.95), SHA)["signal"]
weak = E.build_signal(interp(confidence=0.4), loc(confidence=0.4), SHA)["signal"]
ok("importance rises with evidence", strong["importance"] > weak["importance"])

# A confident read of an unconfident place must not inherit the read's confidence.
placed = E.build_signal(interp(confidence=0.95), loc(confidence=0.4), SHA)["signal"]
ok("shaky geolocation drags importance down", placed["importance"] < strong["importance"])

print(f"\nimint_event: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
