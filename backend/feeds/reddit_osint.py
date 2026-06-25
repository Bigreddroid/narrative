"""
Reddit OSINT — free open-source social signal. Pulls hot posts from a set of
world-news / geopolitics / defense subreddits.

Two fetch paths, picked automatically:
  • OAuth (preferred) — if REDDIT_CLIENT_ID/SECRET are set we get an app-only
    bearer token (client_credentials grant) and read from oauth.reddit.com, which
    has a far higher rate limit and does NOT 403 like the anonymous endpoint.
  • Keyless fallback — the public www.reddit.com/r/{sub}/hot.json endpoint, with a
    descriptive User-Agent, an Accept header, and one backoff+retry on 403/429.
    Reddit aggressively rate-limits/bot-blocks this path, hence the OAuth upgrade.

These posts are NOISY, so unlike the authoritative feeds this module does NOT emit
Signals directly: parse_reddit only normalizes raw post candidates. The LLM triage
agent (backend/services/osint_agent.py) decides relevance, category, geolocation, and
importance before a candidate becomes a NarrativeEvent. Source = 'osint_reddit'.
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

SOURCE = "osint_reddit"
DEFAULT_SUBREDDITS = ["worldnews", "geopolitics", "CredibleDefense"]
# A descriptive UA is mandatory for Reddit; the bare/blank UA is what gets 403'd.
DEFAULT_USER_AGENT = "the-narrative-osint/0.2 (by /u/the-narrative-app; +https://thenarrative.io)"

_OAUTH_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_PUBLIC_HOST = "https://www.reddit.com"
_OAUTH_HOST = "https://oauth.reddit.com"

# Module-level app-only OAuth token cache: {"token": str, "expires_at": float-epoch}.
# Tokens last ~1h; caching avoids re-authenticating on every 30-min poll.
_token_cache: dict = {}
_TOKEN_SKEW_SECONDS = 60.0      # refresh a bit early so we never send an expired token
_RETRY_BACKOFF_SECONDS = 1.5    # one short pause before the single 403/429 retry


def parse_reddit(data: dict, subreddit: str = "") -> list[dict]:
    """Reddit listing JSON → list of raw post-candidate dicts (NOT yet Signals).

    Pure + testable: no I/O. Skips stickied/NSFW posts and anything without an id
    or title. The triage agent consumes these candidates downstream. The JSON shape
    is identical for the public .json and the OAuth endpoints, so this is reused by both.
    """
    children = (((data or {}).get("data") or {}).get("children")) or []
    out: list[dict] = []
    for child in children:
        d = (child or {}).get("data") or {}
        pid = d.get("id")
        title = (d.get("title") or "").strip()
        if not pid or not title:
            continue
        if d.get("stickied") or d.get("over_18"):
            continue
        permalink = d.get("permalink") or ""
        out.append({
            "external_id": f"reddit-{pid}",
            "subreddit": d.get("subreddit") or subreddit,
            "title": title,
            "selftext": (d.get("selftext") or "")[:2000],
            "url": d.get("url") or (f"https://www.reddit.com{permalink}" if permalink else ""),
            "score": int(d.get("score") or 0),
            "num_comments": int(d.get("num_comments") or 0),
            "created_utc": d.get("created_utc"),
        })
    return out


def _oauth_configured(s) -> bool:
    """True when both OAuth credentials are present (the app-only upgrade path)."""
    return bool(s.reddit_client_id and s.reddit_client_secret)


def _cached_token(now: float | None = None) -> str | None:
    """Return a still-valid cached bearer token, or None. Pure (reads module cache)."""
    now = time.time() if now is None else now
    token = _token_cache.get("token")
    if token and _token_cache.get("expires_at", 0.0) > now:
        return token
    return None


def _request_for(sub: str, token: str | None, ua: str, limit: int) -> tuple[str, dict, dict]:
    """Pure: choose endpoint + headers + params for one subreddit fetch.

    With a bearer token → authenticated oauth.reddit.com host (high rate limit).
    Without → public www.reddit.com/.json. raw_json=1 unescapes HTML entities.
    """
    params = {"limit": limit, "raw_json": 1}
    headers = {"User-Agent": ua, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"bearer {token}"
        return f"{_OAUTH_HOST}/r/{sub}/hot", headers, params
    return f"{_PUBLIC_HOST}/r/{sub}/hot.json", headers, params


async def _get_oauth_token(client, s) -> str | None:
    """App-only OAuth (client_credentials). Cached ~1h. None on failure → keyless fallback."""
    cached = _cached_token()
    if cached:
        return cached
    try:
        resp = await client.post(
            _OAUTH_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(s.reddit_client_id, s.reddit_client_secret),
            headers={"User-Agent": s.reddit_user_agent or DEFAULT_USER_AGENT},
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            logger.warning("Reddit OAuth returned no access_token; using keyless endpoint")
            return None
        ttl = float(data.get("expires_in") or 3600)
        _token_cache["token"] = token
        _token_cache["expires_at"] = time.time() + max(0.0, ttl - _TOKEN_SKEW_SECONDS)
        return token
    except Exception as exc:  # noqa: BLE001 — never let auth failure crash ingest; fall back
        logger.warning("Reddit OAuth token fetch failed (%s); using keyless endpoint", exc)
        return None


async def _fetch_subreddit(client, sub: str, token: str | None, ua: str,
                           limit: int, _retried: bool = False) -> list[dict]:
    """Fetch + parse one subreddit. One backoff+retry on 403/429; on 403 the retry
    drops to the keyless endpoint (the token, if any, may be what's being rejected)."""
    url, headers, params = _request_for(sub, token, ua, limit)
    resp = await client.get(url, headers=headers, params=params)
    if resp.status_code in (403, 429) and not _retried:
        logger.warning("Reddit %s for %s (authed=%s) — backing off and retrying once",
                       resp.status_code, url, bool(token))
        await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
        retry_token = None if resp.status_code == 403 else token
        return await _fetch_subreddit(client, sub, retry_token, ua, limit, _retried=True)
    resp.raise_for_status()
    return parse_reddit(resp.json(), sub)


async def fetch_reddit_osint(subreddits: list[str] | None = None, limit: int = 25) -> list[dict]:
    """Fetch hot posts across the configured subreddits → raw candidates.

    Lazy-imports httpx so parse_reddit stays importable in tests without the dep.
    Uses OAuth when credentials are configured, else the hardened keyless endpoint.
    One bad subreddit must not sink the rest.
    """
    import httpx

    from backend.config import get_settings
    s = get_settings()
    subs = subreddits or [x.strip() for x in (s.osint_subreddits or "").split(",") if x.strip()] or DEFAULT_SUBREDDITS
    ua = s.reddit_user_agent or DEFAULT_USER_AGENT

    out: list[dict] = []
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": ua}, follow_redirects=True) as client:
        token = await _get_oauth_token(client, s) if _oauth_configured(s) else None
        for sub in subs:
            try:
                out.extend(await _fetch_subreddit(client, sub, token, ua, limit))
            except Exception as exc:  # noqa: BLE001 — one bad subreddit must not sink the rest
                logger.warning("Reddit fetch failed for r/%s: %s", sub, exc)
                continue
    return out
