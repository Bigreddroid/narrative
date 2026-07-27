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

print(f"\nscraper engine: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
