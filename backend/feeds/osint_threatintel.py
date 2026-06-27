"""
OSINT threat-intel — free, KEYLESS cyber-threat signal from ransomware.live.

This is the one machine-readable auto-ingest source the OSINT Framework integration
adds: most framework entries are interactive investigator tools, but its "Cyber
Threat Intelligence" branch points at a few feeds, of which ransomware.live exposes a
keyless JSON of recent ransomware victims (group, victim org, country, sector).

Like the GDELT/Reddit OSINT sources, this only normalizes raw candidates — the LLM
triage agent (backend/services/osint_agent.py) decides relevance, geolocation and
importance before a candidate becomes a NarrativeEvent. The candidate shape mirrors
gdelt_osint so the same triage agent consumes it. Source = 'osint_threatintel'.
"""

import hashlib
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SOURCE = "osint_threatintel"
FEED_URL = "https://api.ransomware.live/v2/recentvictims"
USER_AGENT = "the-narrative-osint/0.2 (+https://thenarrative.io)"


def _parse_date(s: str | None) -> float | None:
    """ISO-8601 timestamp (e.g. '2026-06-27T18:28:12.666586+00:00') → epoch seconds."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError):
        return None


def parse_threatintel(data: list | None) -> list[dict]:
    """ransomware.live recentvictims JSON → raw post-candidate dicts (NOT Signals).

    Pure + testable: no I/O. Skips entries without a victim, dedupes by (group,
    victim, date). Title carries the signal (the 'ransomware' keyword keeps the
    heuristic triage path working even with no LLM); country/sector add context.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for v in (data or []):
        if not isinstance(v, dict):
            continue
        victim = (v.get("victim") or "").strip()
        if not victim:
            continue
        group = (v.get("group") or "unknown group").strip()
        country = (v.get("country") or "").strip()
        activity = (v.get("activity") or "").strip()
        date = (v.get("attackdate") or v.get("discovered") or "").strip()

        key = f"{group}|{victim}|{date}"
        if key in seen:
            continue
        seen.add(key)
        pid = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

        loc = f" in {country}" if country else ""
        sector = f" [{activity}]" if activity else ""
        url = (v.get("claim_url") or v.get("url") or v.get("domain") or "").strip()
        desc = (v.get("description") or "").strip()

        out.append({
            "external_id": f"threatintel-{pid}",
            # Source context shown to the triage LLM (where Reddit puts the subreddit).
            "subreddit": "ransomware.live",
            # Lead with "ransomware" (no "attack" — that keyword maps to 'conflict'
            # in the heuristic triage, which often runs when no LLM is available).
            "title": f"Ransomware incident: {group} claims {victim}{loc}{sector}",
            "selftext": desc[:500],
            "url": url,
            "score": 0,
            "num_comments": 0,
            "created_utc": _parse_date(date),
        })
    return out


async def fetch_threatintel(maxrecords: int = 60) -> list[dict]:
    """Fetch recent ransomware victims → raw candidates.

    Lazy-imports httpx so parse_threatintel stays importable in tests without the dep.
    Returns [] on any failure (the worker treats an empty run as a no-op).
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                     headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(FEED_URL)
            resp.raise_for_status()
            return parse_threatintel(resp.json())[:maxrecords]
    except Exception as exc:  # noqa: BLE001 — keyless best-effort feed; never sink the run
        logger.warning("threat-intel fetch failed: %s", exc)
        return []
