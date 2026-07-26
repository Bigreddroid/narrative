"""Resolve Google News redirect URLs to the publisher's actual article URL.

WHY THIS EXISTS. Google News RSS does not give us the article's address. It gives us
`news.google.com/rss/articles/CBMi…`, and that URL is not a redirect: fetching it
returns 200 and *stays* on news.google.com, serving a ~600KB Angular interstitial that
only reaches the publisher via JavaScript. So a security analyst who clicks "source
document" in the signal drawer to verify a claim lands on Google, not on the article —
which defeats the one thing an evidence chain is for.

The obvious fix does not work: the `CBMi…` segment base64-decodes to
`08 13 22 <len> AU_yqL…`, an opaque server-side id, NOT a URL. There is nothing to
decode offline. (Older Google News URLs did embed the URL; these do not.)

What does work is asking Google. The interstitial carries a signature/timestamp pair
(`data-n-a-sg` / `data-n-a-ts`), and POSTing those back to the batchexecute
`garturlreq` RPC returns the publisher URL. Verified against live articles.

This endpoint is undocumented, so it is treated as unreliable by construction:
  • every failure degrades to keeping the redirect — the address we have today, so a
    Google-side change can never lose an article, only fail to improve its link;
  • successes are cached, because the RSS window re-offers the same 100 items every
    cycle and each resolution costs a full 600KB fetch (the signature sits in the last
    2KB of the document, so there is no early exit to be had);
  • a per-cycle budget bounds the bandwidth, so a cold start or an outage cannot turn
    one ingest cycle into thousands of requests. Whatever is not resolved this cycle is
    re-offered next cycle, so the backlog drains on its own;
  • an id that keeps failing is abandoned after MAX_ATTEMPTS rather than retried
    forever.

Resolution lives inside `fetch_rss_osint` rather than in a helper each caller must
remember, for the reason this branch already learned the hard way with the evidence
filter: a rule only some callers apply is not a rule.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_ARTICLE_RE = re.compile(r"news\.google\.com/rss/articles/([A-Za-z0-9_\-]+)")
_SG_RE = re.compile(r'data-n-a-sg="([^"]+)"')
_TS_RE = re.compile(r'data-n-a-ts="([^"]+)"')

# The publisher URL never lives on a Google host; if that is what came back, the RPC
# answered but told us nothing, and pretending otherwise would put a link in front of
# an analyst that claims to be the source document and isn't.
_NOT_A_PUBLISHER = re.compile(r"(^|\.)(google|gstatic|googleapis|youtube)\.", re.I)

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"

# ~600KB per resolution. 40 caps a cold cycle at ~24MB; steady state after the cache
# warms is a handful of genuinely new articles per cycle.
DEFAULT_BUDGET = 40
DEFAULT_CONCURRENCY = 6
MAX_ATTEMPTS = 3
_CACHE_CAP = 20_000

_RESOLVED: dict[str, str] = {}
_ATTEMPTS: dict[str, int] = {}


def reset_cache() -> None:
    """Drop the memo. For tests and for the backfill script's own accounting."""
    _RESOLVED.clear()
    _ATTEMPTS.clear()


def article_id(url: str | None) -> str | None:
    """The opaque Google article id, or None if this isn't a Google News article URL."""
    if not url:
        return None
    m = _ARTICLE_RE.search(url)
    return m.group(1) if m else None


def is_gnews_article(url: str | None) -> bool:
    """True only for per-article Google News URLs — a search or section feed URL has
    no article to resolve."""
    return article_id(url) is not None


def publisher_from_url(url: str | None) -> str | None:
    """Host of a resolved URL, as the outlet label ('nytimes.com').

    The registrable host is a FACT derived from the article's address. The publisher's
    display name ("The New York Times") is not recoverable here, and inventing one from
    a lookup table would be fabricating provenance — so the host is what we claim.
    """
    if not url:
        return None
    try:
        host = (urlparse(url).netloc or "").strip().lower()
    except ValueError:
        return None
    if not host or "." not in host:
        return None
    return host[4:] if host.startswith("www.") else host


def parse_batch_response(text: str) -> str | None:
    """Pull the publisher URL out of a batchexecute body, or None.

    The body is `)]}'` followed by length-prefixed JSON chunks. Parsed structurally
    (find the Fbv4je envelope, read its inner `garturlres` payload) rather than by
    scraping the first URL-shaped string out of it, so a change in Google's response
    shape yields None instead of a confidently wrong link.
    """
    if not text:
        return None
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("[["):
            continue
        try:
            chunks = json.loads(line)
        except (ValueError, TypeError):
            continue
        for entry in chunks:
            if not (isinstance(entry, list) and len(entry) > 2):
                continue
            if entry[1] != "Fbv4je" or not isinstance(entry[2], str):
                continue
            try:
                payload = json.loads(entry[2])
            except (ValueError, TypeError):
                continue
            if (isinstance(payload, list) and len(payload) > 1
                    and payload[0] == "garturlres" and isinstance(payload[1], str)):
                url = payload[1]
                host = urlparse(url).netloc
                if url.startswith(("http://", "https://")) and not _NOT_A_PUBLISHER.search(host):
                    return url
    return None


def _batch_payload(art_id: str, ts: str, sg: str) -> str:
    """The `garturlreq` envelope. The 'X' placeholders are Google's own — the RPC only
    reads the article id, timestamp and signature."""
    inner = json.dumps([
        "garturlreq",
        [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None,
          None, None, None, 0, 1],
         "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
        art_id, int(ts), sg,
    ])
    return json.dumps([[["Fbv4je", inner, None, "generic"]]])


async def _resolve_one(client, url: str, art_id: str) -> str | None:
    """Two hops: read the signature off the interstitial, then ask the RPC.

    Returns None on ANY failure — a bad status, a missing signature, a shape we don't
    recognise, a timeout, a connection reset. The caller keeps the redirect.
    """
    try:
        resp = await client.get(url)
        body = resp.text
        if resp.status_code >= 400 or not body:
            logger.debug("gnews interstitial %s: status %s", art_id[:16], resp.status_code)
            return None
        sg, ts = _SG_RE.search(body), _TS_RE.search(body)
        if not (sg and ts):
            # Google served something else (consent wall, error page, layout change).
            logger.debug("gnews interstitial %s carried no signature", art_id[:16])
            return None
        resp2 = await client.post(
            BATCH_URL,
            content=("f.req=" + _quote(_batch_payload(art_id, ts.group(1), sg.group(1)))).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        if resp2.status_code >= 400:
            return None
        return parse_batch_response(resp2.text)
    except Exception as exc:  # noqa: BLE001 — a link improvement must never sink ingest
        logger.debug("gnews resolve failed for %s: %s", art_id[:16], exc)
        return None


def _quote(s: str) -> str:
    from urllib.parse import quote

    return quote(s, safe="")


def _trim_cache() -> None:
    """Keep the memo bounded in a process that runs for weeks."""
    if len(_RESOLVED) > _CACHE_CAP:
        for k in list(_RESOLVED)[: len(_RESOLVED) - _CACHE_CAP]:
            _RESOLVED.pop(k, None)
    if len(_ATTEMPTS) > _CACHE_CAP:
        for k in list(_ATTEMPTS)[: len(_ATTEMPTS) - _CACHE_CAP]:
            _ATTEMPTS.pop(k, None)


async def resolve_urls(urls, *, client=None, budget: int = DEFAULT_BUDGET,
                       concurrency: int = DEFAULT_CONCURRENCY) -> dict[str, str]:
    """{original_url: publisher_url} for whatever could be resolved.

    Non-Google URLs are skipped without a request. Cached ids cost nothing. Only up to
    `budget` uncached ids are attempted; the rest keep their redirect and come back
    next cycle.
    """
    todo: list[tuple[str, str]] = []
    out: dict[str, str] = {}
    seen: set[str] = set()
    for url in urls:
        art_id = article_id(url)
        if not art_id or art_id in seen:
            continue
        seen.add(art_id)
        if art_id in _RESOLVED:
            out[url] = _RESOLVED[art_id]
            continue
        if _ATTEMPTS.get(art_id, 0) >= MAX_ATTEMPTS:
            continue
        if len(todo) < budget:
            todo.append((url, art_id))
    if not todo:
        return out

    owned = client is None
    if owned:
        import httpx

        client = httpx.AsyncClient(timeout=25, follow_redirects=True,
                                   headers={"User-Agent": USER_AGENT})
    sem = asyncio.Semaphore(concurrency)

    async def one(url: str, art_id: str):
        async with sem:
            _ATTEMPTS[art_id] = _ATTEMPTS.get(art_id, 0) + 1
            resolved = await _resolve_one(client, url, art_id)
            if resolved:
                _RESOLVED[art_id] = resolved
                _ATTEMPTS.pop(art_id, None)
                out[url] = resolved

    try:
        await asyncio.gather(*(one(u, a) for u, a in todo))
    finally:
        if owned:
            await client.aclose()
    _trim_cache()
    if todo:
        logger.info("gnews resolve: %d attempted, %d resolved (%d cached)",
                    len(todo), sum(1 for u, _ in todo if u in out), len(_RESOLVED))
    return out


def apply_resolutions(items: list[dict], resolved: dict[str, str]) -> int:
    """Rewrite `url` in place for resolved items. Returns how many changed.

    ONLY `url` is touched. `external_id` keys event dedupe and is derived from the
    original link — rewriting it would make every already-ingested Google item look
    brand new and duplicate it across the deck.
    """
    n = 0
    for it in items:
        target = resolved.get(it.get("url") or "")
        if target and target != it.get("url"):
            it["url"] = target
            n += 1
    return n
