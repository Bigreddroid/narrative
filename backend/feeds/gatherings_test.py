"""Tests for the keyless public-gatherings feed. No network: payloads are canned."""

from datetime import datetime, timezone

from backend.feeds import gatherings as g

passed = failed = 0


def ok(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {label}")
    else:
        failed += 1
        print(f"  FAIL {label}")


def _row(name, start, point, country="India"):
    r = {"itemLabel": {"value": name}, "start": {"value": start}}
    if point:
        r["coord"] = {"value": point}
    if country:
        r["countryLabel"] = {"value": country}
    return r


PAYLOAD = {"results": {"bindings": [
    _row("2026 Badminton World Championships", "2026-08-17T00:00:00Z",
         "Point(77.208888888 28.613888888)"),
    # same event, second binding from the UNION -- must fold, not double-count
    _row("2026 Badminton World Championships", "2026-08-17T00:00:00Z",
         "Point(77.208888888 28.613888888)"),
    _row("2026 Mediterranean Games", "2026-08-21T00:00:00Z",
         "Point(17.243055555 40.471111111)", "Italy"),
    _row("no coordinate event", "2026-08-30T00:00:00Z", None),
    _row("Q12345678", "2026-08-30T00:00:00Z", "Point(1.0 2.0)"),
]}}


# ── coordinates ──────────────────────────────────────────────────────────────
ok("WKT Point is read as (lat, lng), not (lng, lat)",
   g.parse_point("Point(77.208888888 28.613888888)") == (28.613888888, 77.208888888))
ok("a malformed point yields None rather than a wrong coordinate",
   g.parse_point("Point(nonsense)") is None)
ok("an empty coordinate yields None", g.parse_point(None) is None and g.parse_point("") is None)

# ── parsing ──────────────────────────────────────────────────────────────────
out = g.parse_response(PAYLOAD)
ok("duplicate UNION rows fold to one gathering, so one crowd is not counted five times",
   sum(1 for x in out if x["name"].startswith("2026 Badminton")) == 1)
ok("an event with no coordinate is dropped, not placed at null island",
   all(x["name"] != "no coordinate event" for x in out))
ok("an unlabelled Q-id is dropped rather than shown as a number on a security deck",
   all(not x["name"].startswith("Q1234") for x in out))
ok("surviving gatherings carry name, date and coordinates",
   all(x["name"] and x["date"] and x["lat"] is not None and x["lng"] is not None
       for x in out))
ok("results are ordered by date", [x["date"] for x in out] == sorted(x["date"] for x in out))
ok("Delhi gathering keeps its real coordinates",
   any(abs(x["lat"] - 28.6138) < 0.01 and abs(x["lng"] - 77.2089) < 0.01 for x in out))

# ── degradation ──────────────────────────────────────────────────────────────
ok("a shape we do not recognise yields [] rather than raising",
   g.parse_response({}) == [] and g.parse_response({"results": {}}) == []
   and g.parse_response(None) == [])

# ── query ────────────────────────────────────────────────────────────────────
q = g.build_query(60, 300, now=datetime(2026, 7, 27, tzinfo=timezone.utc))
ok("the window starts today", "2026-07-27T00:00:00Z" in q)
ok("the window ends `days` later", "2026-09-25T00:00:00Z" in q)
ok("the query asks for a location hop, not just a direct coordinate",
   "wdt:P276" in q and "wdt:P1001" in q and "wdt:P625" in q)
ok("the limit is applied", "LIMIT 300" in q)

# ── failure is not emptiness ─────────────────────────────────────────────────
# The whole point of this layer: a failed fetch must never render as "no gatherings
# near your offices", which is the same lie the holiday layer was fixed for.
import asyncio  # noqa: E402

import httpx  # noqa: E402


class _Unreachable:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, *a, **kw):
        raise RuntimeError("wikidata unreachable")


g.reset_cache()
_real_client = httpx.AsyncClient
httpx.AsyncClient = lambda *a, **kw: _Unreachable()
try:
    _res = asyncio.run(g.fetch_gatherings(days=30))
finally:
    httpx.AsyncClient = _real_client
ok("an unreachable source returns None, not an [] that reads as 'none nearby'",
   _res is None)

# -- gatherings_now: never blocks the calendar response -------------------------
# The regression this guards: fetch_gatherings is allowed 75s (Wikidata's subclass
# walk really is that slow), but the deck gives the WHOLE calendar request 15s. When
# the route awaited that fetch inline, a cold cache did not merely lose the gatherings
# layer -- it blew the client timeout for the entire response, so the live 43-country
# HOLIDAY layer went blank too, and the all-layers strip called both "checked".
import time as _time  # noqa: E402

g.reset_cache()


async def _cold_read():
    t0 = _time.monotonic()
    res = g.gatherings_now(days=30)
    elapsed = _time.monotonic() - t0
    for t in list(g._TASKS):
        t.cancel()
    return res, elapsed


_res, _elapsed = asyncio.run(_cold_read())
ok("a cold cache returns immediately instead of blocking the whole request",
   _elapsed < 1.0)
ok("a cold read is None ('not checked'), never [] ('no crowds near you')",
   _res is None)

g.reset_cache()
g._CACHE[30] = (_time.time(), [{"name": "X", "date": "2026-08-01", "lat": 1.0,
                               "lng": 2.0, "country": None, "source": "wikidata"}])
ok("a warm cache is served synchronously", g.gatherings_now(days=30) is not None)

g.reset_cache()
g._CACHE[30] = (_time.time() - (g._TTL + 1), [{"name": "stale"}])
ok("a cache older than the TTL is not served", g.cached(30) is None)


async def _burst():
    for _ in range(5):
        g.gatherings_now(days=45)
    n = len(g._INFLIGHT)
    for t in list(g._TASKS):
        t.cancel()
    return n


g.reset_cache()
ok("a burst of cold reads coalesces into ONE refresh", asyncio.run(_burst()) == 1)

g.reset_cache()

print(f"\ngatherings: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
