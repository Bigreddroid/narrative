"""
advisories — official government travel advice, fetched and parsed. Never written.

The incumbent ships ~143 advice sheets. We do not have a research desk and we are
not going to pretend otherwise, so every word of guidance here comes from a named
government that published it, with its date and a link back to the original. Writing
our own would be exactly the fabrication this project refuses everywhere else.

Two authorities, both keyless and both verified reachable from the container:
  * US State Department — RSS of all Travel Advisories (213 countries).
  * UK FCDO — GOV.UK content API, one JSON document per country, six named parts.

🔴 THEIR SCALES ARE NOT THE SAME SCALE, AND ARE NOT MERGED. State uses Level 1-4;
FCDO uses alert statuses like "avoid_all_travel_to_parts". They are different
instruments built by different governments for different publics, and averaging them
into one 0-5 number — the thing the incumbent's console does — invents a precision
neither authority claims. Each advisory keeps its own issuer's vocabulary, and the
UI shows both side by side rather than reconciling them.

Parsing is pure and separated from fetching (``parse_state_rss`` / ``parse_fcdo``) so
the test suite exercises the real shapes without touching the network.
"""

import html
import logging
import re
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

STATE_RSS = "https://travel.state.gov/_res/rss/TAsTWs.xml"
FCDO_BASE = "https://www.gov.uk/api/content/foreign-travel-advice"

# Source strings are prefixed `gov_` on purpose: source_reliability.py's provenance
# prior maps "gov"/"official" to Admiralty B ("usually reliable"), so these grade
# through the SAME path as any other source rather than getting a special case.
SOURCE_STATE = "gov_us_state_dept"
SOURCE_FCDO = "gov_uk_fcdo"

AUTHORITY_LABELS = {
    SOURCE_STATE: "U.S. Department of State",
    SOURCE_FCDO: "UK Foreign, Commonwealth & Development Office",
}

_UA = {"User-Agent": "Mozilla/5.0 (compatible; TheNarrative/1.0)"}
_TIMEOUT = 30.0

# "Belgium - Level 2: Exercise Increased Caution"
_TITLE_RE = re.compile(r"^\s*(?P<country>.+?)\s*-\s*Level\s*(?P<level>\d)\s*:\s*(?P<label>.+?)\s*$")
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str, limit: int = 1200) -> str:
    """Plain text from an HTML fragment.

    Deliberately not a rewrite: entities are unescaped and tags removed so the text
    can be read in a list or an email, but no words are added, dropped or reordered.
    Truncation is marked, because a silently clipped advisory reads as a complete one.
    """
    text = _TAG_RE.sub(" ", s or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + " […]"
    return text


def _parse_rfc822(value: str):
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S", "%a, %d %b %Y"):
        try:
            dt = datetime.strptime(value.strip(), fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def parse_state_rss(xml: str) -> list[dict]:
    """Advisories from the State Department RSS. Pure — no network."""
    out: list[dict] = []
    for block in re.findall(r"<item>(.*?)</item>", xml or "", re.S):
        def field(tag: str) -> str:
            m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
            return (m.group(1) if m else "").strip()

        title = html.unescape(_TAG_RE.sub("", field("title"))).strip()
        m = _TITLE_RE.match(title)
        if not m:
            # Worldwide Cautions and other non-country items carry no level. Skipped
            # rather than filed under a country they do not describe.
            continue

        desc = field("description")
        desc = re.sub(r"^\s*<!\[CDATA\[|\]\]>\s*$", "", desc, flags=re.S)
        published = _parse_rfc822(field("pubDate"))

        out.append({
            "authority": SOURCE_STATE,
            "country": m.group("country").strip(),
            # The issuer's OWN vocabulary, kept verbatim. "Level 2" means what the
            # State Department says it means and is not converted to anything.
            "level_code": f"L{m.group('level')}",
            "level_label": m.group("label").strip(),
            "summary": _strip_html(desc),
            "url": field("link"),
            "published_at": published,
            "sections": {},
        })
    return out


def parse_fcdo(doc: dict) -> dict | None:
    """One country advisory from a GOV.UK content document. Pure — no network."""
    if not isinstance(doc, dict) or not doc.get("title"):
        return None
    details = doc.get("details") or {}
    country = (details.get("country") or {}).get("name") or doc.get("title", "").strip()
    if not country:
        return None

    statuses = details.get("alert_status") or []
    # FCDO's own machine vocabulary, preserved. "No specific alert" is a real state
    # and is said in words rather than left blank, which reads as missing data.
    level_code = ",".join(statuses) if statuses else "none"
    level_label = (", ".join(s.replace("_", " ") for s in statuses).capitalize()
                   if statuses else "No specific travel alert")

    sections = {}
    for part in details.get("parts") or []:
        slug, body = part.get("slug"), part.get("body")
        if slug and body:
            sections[slug] = _strip_html(body, limit=2500)

    published = None
    raw = doc.get("public_updated_at") or details.get("updated_at")
    if raw:
        try:
            published = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            published = None

    return {
        "authority": SOURCE_FCDO,
        "country": country,
        "level_code": level_code,
        "level_label": level_label,
        # change_description is what the FCDO itself says changed — far more useful to
        # a security team than a summary we would have to compose.
        "summary": _strip_html(details.get("change_description") or doc.get("description") or ""),
        "url": "https://www.gov.uk" + (doc.get("base_path") or ""),
        "published_at": published,
        "sections": sections,
    }


def fcdo_slug(country: str) -> str:
    """GOV.UK's path segment for a country name."""
    s = re.sub(r"[^a-z0-9]+", "-", str(country or "").lower()).strip("-")
    # GOV.UK drops the leading article that several of our canonical names carry.
    for prefix in ("the-",):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s


async def fetch_state_dept() -> list[dict]:
    """Every State Department advisory in one request."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True, headers=_UA) as c:
            r = await c.get(STATE_RSS)
            r.raise_for_status()
            return parse_state_rss(r.text)
    except Exception as exc:  # noqa: BLE001 — an unreachable authority is not a crash
        logger.warning("State Dept advisories unavailable: %s", exc)
        return []


async def fetch_fcdo(country: str) -> dict | None:
    """One country's FCDO advisory, or None if that country has no sheet.

    A 404 is a legitimate answer — the FCDO does not publish for every place — and is
    returned as None rather than raised, so one missing country cannot end an ingest.
    """
    slug = fcdo_slug(country)
    if not slug:
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True, headers=_UA) as c:
            r = await c.get(f"{FCDO_BASE}/{slug}")
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return parse_fcdo(r.json())
    except Exception as exc:  # noqa: BLE001
        logger.warning("FCDO advisory for %s unavailable: %s", country, exc)
        return None
