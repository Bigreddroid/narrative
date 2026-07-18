"""
OSINT social — free, KEYLESS real-world chatter from the Mastodon public tag timeline.

Mastodon (the largest open ActivityPub network) exposes an unauthenticated
`GET /api/v1/timelines/tag/{tag}` endpoint returning recent public Status objects for
a hashtag. Following OSINT/geopolitics/breakingnews tags gives a real-time social
signal at $0 — the one first-party social source alongside GDELT (news), RSS/Atom,
and ransomware.live (threat-intel).

Like the other OSINT sources this only normalizes raw candidates — the LLM triage
agent (backend/services/osint_agent.py) decides relevance, geolocation and importance
before a candidate becomes a NarrativeEvent. The candidate shape mirrors osint_threatintel
so the same triage agent consumes it. Source = 'osint_mastodon'.
"""

import hashlib
import html
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

SOURCE = "osint_mastodon"
USER_AGENT = "the-narrative-osint/0.2 (+https://thenarrative.io)"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(raw: str | None) -> str:
    """Mastodon `content` is sanitized HTML (<p>, <a>, <br>). Drop the tags, unescape
    entities and collapse whitespace to a plain-text line the triage LLM can read.
    Pure + dependency-free (no bs4) so parse_mastodon stays importable in tests."""
    if not raw:
        return ""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", raw))).strip()


def _parse_iso(s: str | None) -> float | None:
    """ISO-8601 timestamp (e.g. '2026-06-27T18:28:12.000Z') → epoch seconds."""
    if not s:
        return None
    try:
        # Mastodon uses a trailing 'Z'; fromisoformat only learned that in 3.11, so
        # normalize it to an explicit offset for older interpreters too.
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def parse_mastodon(statuses: list | None, tag: str) -> list[dict]:
    """Mastodon tag-timeline JSON (list of Status objects) → raw post-candidate dicts.

    Pure + testable: no I/O. Skips reblogs (they carry no original text of their own),
    bot posts and empty content. Dedupes within the batch by status id. Title carries
    the signal; the source-context slot ('mastodon #tag') gives the triage LLM
    provenance the way Reddit gives it the subreddit.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for s in (statuses or []):
        if not isinstance(s, dict):
            continue
        # A reblog (boost) has an empty top-level content and a nested `reblog` — skip
        # it rather than ingest a blank; the original will surface on its own timeline.
        if s.get("reblog"):
            continue
        account = s.get("account") or {}
        if account.get("bot"):
            continue

        text = _strip_html(s.get("content"))
        card = s.get("card") or {}
        card_title = (card.get("title") or "").strip()
        if not text and not card_title:
            continue

        sid = str(s.get("id") or "")
        if not sid or sid in seen:
            continue
        seen.add(sid)
        pid = hashlib.sha1(sid.encode("utf-8")).hexdigest()[:16]

        # Lead the title with the post text (falling back to the link-card headline);
        # keep it short so it reads as a headline, and stash the full text in selftext.
        title = (text or card_title)[:200]

        out.append({
            "external_id": f"mastodon-{pid}",
            # Source context shown to the triage LLM (where Reddit puts the subreddit).
            "subreddit": f"mastodon #{tag}",
            "title": title,
            "selftext": text[:500],
            "url": (s.get("url") or s.get("uri") or "").strip(),
            "score": int(s.get("favourites_count") or 0),
            "num_comments": int(s.get("replies_count") or 0),
            "created_utc": _parse_iso(s.get("created_at")),
        })
    return out


async def fetch_mastodon(instance: str = "mastodon.social",
                         tags: str = "osint,geopolitics,breakingnews",
                         limit: int = 40) -> list[dict]:
    """Fetch recent public posts for each hashtag → merged raw candidates.

    One keyless GET per tag against the instance's public tag timeline. Lazy-imports
    httpx so parse_mastodon stays importable in tests without the dep. Returns [] on
    any failure (the worker treats an empty run as a no-op); a single failing tag is
    skipped without sinking the rest.
    """
    import httpx

    tag_list = [t.strip().lstrip("#") for t in (tags or "").split(",") if t.strip()]
    if not tag_list:
        return []

    out: list[dict] = []
    seen: set[str] = set()
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                     headers={"User-Agent": USER_AGENT}) as client:
            for tag in tag_list:
                url = f"https://{instance}/api/v1/timelines/tag/{tag}"
                try:
                    resp = await client.get(url, params={"limit": limit})
                    resp.raise_for_status()
                    for cand in parse_mastodon(resp.json(), tag):
                        if cand["external_id"] in seen:
                            continue
                        seen.add(cand["external_id"])
                        out.append(cand)
                except Exception as exc:  # noqa: BLE001 — one bad tag must not sink the rest
                    logger.warning("mastodon tag '%s' fetch failed: %s", tag, exc)
    except Exception as exc:  # noqa: BLE001 — keyless best-effort feed; never sink the run
        logger.warning("mastodon fetch failed: %s", exc)
        return []
    return out
