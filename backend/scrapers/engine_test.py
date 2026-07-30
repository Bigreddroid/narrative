"""Tests for the scrape engine's bookkeeping. No network, no DB: both are faked.

These exist because of a measured production failure: 570 of 688 active sources had
NEVER been scraped (last_scraped_at IS NULL) and scrape_error_count was 0 on every
single one, including feeds returning 404. Two independent causes, both invisible:

  1. hazard_ingest_worker creates a `sources` row per distinct PUBLISHER name for
     corroboration counting, with url="" and no rss_url. `is_active` defaults to True
     and `scrape_method` defaults to "rss", so the scrape worker picked them all up as
     if they were feeds, fell through the method dispatch, and returned early.
  2. fetch_rss swallowed every exception and returned [], which scrape_source could
     not tell apart from "the feed is fine and had nothing new". So a dead feed never
     recorded an error, and never recorded an attempt either.
"""

import asyncio
from datetime import datetime, timezone

from backend.models.source import Source
from backend.scrapers import engine as e
from backend.scrapers import rss_parser as rp

passed = failed = 0


def ok(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {label}")
    else:
        failed += 1
        print(f"  FAIL {label}")


# ── fakes ────────────────────────────────────────────────────────────────────
class _Result:
    def __init__(self, rows=(), rowcount=0):
        self._rows = rows
        self.rowcount = rowcount

    def __iter__(self):
        return iter(self._rows)


class _DB:
    def __init__(self):
        self.added = []

    async def execute(self, stmt):
        # The only SELECT here is the url_hash dedup probe; treat every article as new.
        return _Result(rows=(), rowcount=1)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


def _source(**kw):
    base = dict(name="Feed", url="https://example.com", rss_url="https://example.com/rss",
                scrape_method="rss", is_active=True, scrape_error_count=0,
                last_scraped_at=None)
    base.update(kw)
    return Source(**base)


def _article(u="https://example.com/a"):
    return {"title": "T", "url": u, "url_hash": "h-" + u, "content": "c", "published_at": None}


# ── scrapeability: a publisher attribution row is NOT a feed ─────────────────
# The whole 570-source hole. These rows exist so corroboration can count distinct
# publishers; they are not something to fetch, and handing them to the scraper made
# every run log 570 warnings and leave 570 rows looking permanently un-attempted.
ok("a publisher row (no url, no rss_url) is not scrapeable",
   e.is_scrapeable(_source(url="", rss_url=None)) is False)
ok("an rss source with an empty rss_url is not scrapeable",
   e.is_scrapeable(_source(rss_url="")) is False)
ok("a real rss feed is scrapeable", e.is_scrapeable(_source()) is True)
ok("a bs4 source is scrapeable on its page url, not an rss_url",
   e.is_scrapeable(_source(scrape_method="bs4", rss_url=None)) is True)
ok("a bs4 source with no page url is not scrapeable",
   e.is_scrapeable(_source(scrape_method="bs4", rss_url=None, url="")) is False)


# ── a failed fetch must be RECORDED, not silently swallowed ──────────────────
async def _run(source, feed_result):
    async def fake_fetch(rss_url, name):
        if isinstance(feed_result, Exception):
            raise feed_result
        return feed_result
    real = e.fetch_rss
    e.fetch_rss = fake_fetch
    try:
        return await e.scrape_source(source, _DB())
    finally:
        e.fetch_rss = real


s = _source(scrape_error_count=2)
asyncio.run(_run(s, None))          # None == "could not fetch"
ok("a failed fetch increments scrape_error_count instead of leaving it at 0",
   s.scrape_error_count == 3)
ok("a failed fetch still records that we ATTEMPTED it",
   s.last_scraped_at is not None)

s = _source(scrape_error_count=5)
asyncio.run(_run(s, []))            # [] == "fetched fine, nothing in it"
ok("an empty-but-successful fetch clears the error count",
   s.scrape_error_count == 0)
ok("an empty-but-successful fetch records the attempt",
   s.last_scraped_at is not None)

s = _source(scrape_error_count=4)
scraped, new = asyncio.run(_run(s, [_article()]))
ok("a good fetch clears the error count", s.scrape_error_count == 0)
ok("a good fetch reports what it scraped", scraped == 1)

# An unscrapeable row must not be silently counted as a healthy check.
s = _source(url="", rss_url=None, last_scraped_at=None)
asyncio.run(_run(s, []))
ok("an unscrapeable row is not stamped as successfully scraped",
   s.last_scraped_at is None)


# ── fetch_rss: None means 'could not check', [] means 'checked, empty' ───────
# Same idiom the gatherings feed already uses. Conflating them is what made a 404
# feed indistinguishable from a quiet one.
import httpx  # noqa: E402


class _Resp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=None)


class _Client:
    def __init__(self, behaviour):
        self._b = behaviour

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url):
        if isinstance(self._b, Exception):
            raise self._b
        return self._b


def _with_client(behaviour, coro_factory):
    real = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: _Client(behaviour)
    try:
        return asyncio.run(coro_factory())
    finally:
        httpx.AsyncClient = real


_r = _with_client(RuntimeError("dns"), lambda: rp.fetch_rss("http://x/rss", "X"))
ok("an unreachable feed returns None, not [] that reads as 'nothing new'", _r is None)

_r = _with_client(_Resp(404), lambda: rp.fetch_rss("http://x/rss", "X"))
ok("a 404 feed returns None rather than an empty success", _r is None)

_r = _with_client(_Resp(200, "<rss><channel></channel></rss>"),
                  lambda: rp.fetch_rss("http://x/rss", "X"))
ok("a reachable feed with no items returns [] — a real answer, not a failure",
   _r == [])

# ── quarantine: skip a dead feed for a day, but never retire it silently ─────
# 19 of 118 feeds are dead; each costs a full HTTP timeout every cycle (~9 min a run
# spent re-confirming what we already know). Quarantine is a SCHEDULING decision — the
# row stays active and keeps its error count, so /admin/sources still reports it as a
# failing feed rather than it quietly vanishing from the register.
from datetime import timedelta  # noqa: E402

NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

s = _source(scrape_error_count=e.QUARANTINE_AFTER, last_scraped_at=NOW - timedelta(hours=1))
ok("a feed past the failure bar is skipped this cycle", e.is_quarantined(s, NOW) is True)

s = _source(scrape_error_count=e.QUARANTINE_AFTER - 1, last_scraped_at=NOW - timedelta(hours=1))
ok("a feed below the bar is still attempted", e.is_quarantined(s, NOW) is False)

s = _source(scrape_error_count=99,
            last_scraped_at=NOW - timedelta(hours=e.QUARANTINE_RETRY_HOURS + 1))
ok("quarantine EXPIRES, so a publisher that moved its feed is found again",
   e.is_quarantined(s, NOW) is False)

s = _source(scrape_error_count=99, last_scraped_at=None)
ok("a never-attempted feed is never quarantined", e.is_quarantined(s, NOW) is False)

s = _source(scrape_error_count=99,
            last_scraped_at=NOW.replace(tzinfo=None) - timedelta(hours=1))
ok("a naive stored timestamp does not raise against an aware now",
   e.is_quarantined(s, NOW) is True)

# Recovery is automatic: scrape_source zeroes the streak on any successful read.
s = _source(scrape_error_count=99, last_scraped_at=NOW - timedelta(hours=1))
asyncio.run(_run(s, [_article()]))
ok("one good read clears the streak, releasing the feed from quarantine",
   s.scrape_error_count == 0 and e.is_quarantined(s, NOW) is False)

# ── yield health: "answered" and "delivered" are different facts ─────────────
# Measured live: Brookings and The Defense Post return HTTP 200 with ZERO items and
# have produced 0 articles ever; Straits Times and Crisis Group return 10 items but
# nothing new since Jul 13. All four reported scrape_error_count=0 and a
# last_scraped_at of minutes ago — identical to a healthy feed. An empty answer is
# correctly a success (the feed responded), which is exactly why success alone cannot
# carry this signal.

s = _source()
asyncio.run(_run(s, [_article()]))
ok("a real yield stamps last_article_at", s.last_article_at is not None)

s = _source(last_article_at=None)
asyncio.run(_run(s, []))
ok("an EMPTY answer does not stamp last_article_at, though it is still a success",
   s.last_article_at is None and s.scrape_error_count == 0
   and s.last_scraped_at is not None)

# The regression that matters: an empty answer must not look like delivery.
s = _source(last_article_at=NOW - timedelta(days=30))
asyncio.run(_run(s, []))
ok("an empty answer leaves an OLD yield timestamp untouched (no false freshness)",
   s.last_article_at == NOW - timedelta(days=30))

ok("a feed reading and delivering is ok",
   e.feed_health(_source(last_article_at=NOW - timedelta(hours=2)), NOW) == "ok")

ok("a feed that answers but has NEVER delivered is never_yielded — the Brookings case",
   e.feed_health(_source(last_article_at=None), NOW) == "never_yielded")

ok("a feed delivering nothing for longer than the bar is stalled — the Straits Times case",
   e.feed_health(_source(last_article_at=NOW - timedelta(days=e.STALE_AFTER_DAYS + 1)),
                 NOW) == "stalled")

ok("a feed just inside the bar is still ok, so a quiet weekend is not an alarm",
   e.feed_health(_source(last_article_at=NOW - timedelta(days=e.STALE_AFTER_DAYS - 1)),
                 NOW) == "ok")

ok("an unreadable feed reports failing, not stalled — the cause is not guessed",
   e.feed_health(_source(scrape_error_count=1, last_article_at=None), NOW) == "failing")

ok("past the failure bar it reports quarantined",
   e.feed_health(_source(scrape_error_count=e.QUARANTINE_AFTER), NOW) == "quarantined")

ok("a publisher-attribution row is not_a_feed, not a dead one",
   e.feed_health(_source(url="", rss_url=None), NOW) == "not_a_feed")

ok("a hand-disabled source is disabled, not failing",
   e.feed_health(_source(is_active=False), NOW) == "disabled")

ok("a naive stored yield timestamp does not raise against an aware now",
   e.feed_health(_source(last_article_at=(NOW - timedelta(days=30)).replace(tzinfo=None)),
                 NOW) == "stalled")

print(f"\nscraper engine: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
