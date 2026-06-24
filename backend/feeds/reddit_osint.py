"""
Reddit OSINT — free, keyless social-media signal. Pulls hot posts from a set of
world-news / geopolitics / defense subreddits via the public .json endpoints.

These posts are NOISY, so unlike the authoritative feeds this module does NOT emit
Signals directly: parse_reddit only normalizes raw post candidates. The LLM triage
agent (backend/services/osint_agent.py) decides relevance, category, geolocation, and
importance before a candidate becomes a NarrativeEvent. Source = 'osint_reddit'.

Public .json needs a descriptive User-Agent and is rate-limited; one poll / 30 min at
low volume is fine. OAuth (reddit_client_id/secret) is the documented upgrade path if
volume grows — added as optional config, same pattern as the other keyed feeds.
"""

SOURCE = "osint_reddit"
DEFAULT_SUBREDDITS = ["worldnews", "geopolitics", "CredibleDefense"]


def parse_reddit(data: dict, subreddit: str = "") -> list[dict]:
    """Reddit listing JSON → list of raw post-candidate dicts (NOT yet Signals).

    Pure + testable: no I/O. Skips stickied/NSFW posts and anything without an id
    or title. The triage agent consumes these candidates downstream.
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


async def fetch_reddit_osint(subreddits: list[str] | None = None, limit: int = 25) -> list[dict]:
    """Fetch hot posts across the configured subreddits → raw candidates.

    Lazy-imports httpx so parse_reddit stays importable in tests without the dep.
    One bad subreddit must not sink the rest.
    """
    import httpx

    from backend.config import get_settings
    s = get_settings()
    subs = subreddits or [x.strip() for x in (s.osint_subreddits or "").split(",") if x.strip()] or DEFAULT_SUBREDDITS
    ua = s.reddit_user_agent or "the-narrative-osint/0.1 (+https://thenarrative.io)"

    out: list[dict] = []
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": ua}) as client:
        for sub in subs:
            try:
                resp = await client.get(
                    f"https://www.reddit.com/r/{sub}/hot.json",
                    params={"limit": limit, "raw_json": 1},
                )
                resp.raise_for_status()
                out.extend(parse_reddit(resp.json(), sub))
            except Exception:  # noqa: BLE001 — one bad subreddit must not sink the rest
                continue
    return out
