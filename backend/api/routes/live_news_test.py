"""Property test for live-news tier gating (no network/DB).
Calls the route handler directly with a duck-typed user; iptv-org expansion is off
by default so there is no outbound HTTP.
Run from repo root:  python -m backend.api.routes.live_news_test
"""

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.api.routes.live_news import list_streams, LIVE_NEWS_CHANNELS, _FREE_CHANNEL_IDS

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


class _FakeUser:  # the handler only reads user.tier
    def __init__(self, tier):
        self.tier = tier


# ── free tier → small taster only ────────────────────────────────────────────
free = asyncio.run(list_streams(user=_FakeUser("free")))
ok("free tier → only taster channels", free["total"] == len(_FREE_CHANNEL_IDS) == 2)
ok("free tier ids are exactly the taster set", {c["id"] for c in free["channels"]} == _FREE_CHANNEL_IDS)
ok("free tier label echoed", free["tier"] == "free")

# ── paid tier → full curated set ─────────────────────────────────────────────
pro = asyncio.run(list_streams(user=_FakeUser("pro")))
ok("paid tier → full curated set", pro["total"] == len(LIVE_NEWS_CHANNELS))
ok("paid tier includes a paid-only channel", any(c["id"] == "france24-en" for c in pro["channels"]))
ok("paid tier label echoed", pro["tier"] == "pro")
ok("every channel exposes id + src + type",
   all(c.get("id") and c.get("src") and c.get("type") in ("hls", "youtube") for c in pro["channels"]))

print(f"\nlive_news: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
