"""
Single source of truth for the event category taxonomy AND the intelligence-
discipline (multi-INT) taxonomy. Import from here instead of re-declaring category
lists — historically the same list was duplicated across synthesize.py,
osint_agent.py, and consensus_mapper.py and drifted.

Two distinct, pre-existing category vocabularies live in the codebase; this module
tracks both rather than force-unifying them (unification is a separate, higher-risk
cleanup that would change what the feed filter buttons do):

  * CATEGORIES      — the 13 feed/OSINT event-type keys (canonical; == synthesize.SECTOR_MAP keys).
  * LLM_CATEGORIES  — the 7 values the article-cluster LLM mapper emits (consensus_mapper prompt).

The multi-INT layer sits ON TOP of both: every event is tagged with an
`int_discipline` derived deterministically (no LLM) from its (source, category) via
`discipline_for()`. Source is the strongest signal (a USGS feed is always MASINT
regardless of category); category is the fallback and is mapped across BOTH
vocabularies so the tag is correct whichever path created the event.

$0/local doctrine: this is pure data + a pure function. No I/O, no LLM.
"""

# ── Event category vocabularies (pre-existing; do not reorder casually) ──────────

# Canonical feed/OSINT event-type categories — kept in lockstep with
# feeds/synthesize.py SECTOR_MAP (guarded by an assert in that module).
CATEGORIES: tuple[str, ...] = (
    "disaster", "wildfire", "storm", "flood", "drought", "volcano",
    "conflict", "unrest", "cyber", "sanction", "space", "market", "disinfo",
)

# The separate enum the LLM cluster-mapper is instructed to choose from. Same
# values as consensus_mapper's prompt — centralized here so it can't drift.
LLM_CATEGORIES: tuple[str, ...] = (
    "geopolitics", "economy", "climate", "health", "technology", "conflict", "policy",
)

# ── Intelligence disciplines (multi-INT) ────────────────────────────────────────

HUMINT, SIGINT, IMINT, GEOINT, MASINT, FININT, CYBINT = (
    "HUMINT", "SIGINT", "IMINT", "GEOINT", "MASINT", "FININT", "CYBINT",
)
DISCIPLINES: tuple[str, ...] = (HUMINT, SIGINT, IMINT, GEOINT, MASINT, FININT, CYBINT)

# Source → discipline: collectors whose provenance ALONE fixes the discipline,
# independent of the event's category. Checked first in discipline_for().
SOURCE_DISCIPLINE: dict[str, str] = {
    # Hazard/measurement feeds → MASINT
    "usgs": MASINT, "nws": MASINT, "nhc": MASINT, "gdacs": MASINT,
    "launchlibrary": MASINT,
    # Cyber feeds → CYBINT
    "cisa": CYBINT, "osint_threatintel": CYBINT,
    # Financial/sanctions → FININT
    "opensanctions": FININT,
    # Interpreted operator-supplied imagery → IMINT. Provenance alone fixes this: the
    # event was created by reading an image (services/imint_event.py), whatever the
    # imagery happens to depict. Until this entry existed, IMINT was declared in
    # DISCIPLINES but unreachable — no source and no category resolved to it, so the
    # /int IMINT panel could never be anything but empty.
    "imint": IMINT,
    # NOTE: general-news OSINT sources (osint_gdelt/osint_rss/osint_reddit/
    # osint_mastodon, gdelt) carry varied categories, so they intentionally fall
    # through to category.
    # NOTE: GEOINT remains intentionally unreachable for now — no collector produces a
    # purely geospatial event yet. /geolocate is a read-out, and imagery it places is
    # IMINT (the image is the source), not GEOINT.
}

# Category → discipline: covers BOTH vocabularies (feed CATEGORIES + LLM_CATEGORIES)
# plus a few frontend display spellings, so discipline_for is correct whichever
# path assigned the category. Fallback when SOURCE_DISCIPLINE has no entry.
CATEGORY_DISCIPLINE: dict[str, str] = {
    # feed CATEGORIES
    "disaster": MASINT, "wildfire": MASINT, "storm": MASINT, "flood": MASINT,
    "drought": MASINT, "volcano": MASINT, "space": MASINT,
    "conflict": HUMINT, "unrest": HUMINT, "disinfo": HUMINT,
    "cyber": CYBINT,
    "sanction": FININT, "market": FININT,
    # LLM_CATEGORIES
    "geopolitics": HUMINT, "policy": HUMINT, "health": HUMINT,
    "climate": MASINT,
    "economy": FININT,
    "technology": CYBINT,
    # frontend display spellings seen in colors.js / FeedHeader
    "economics": FININT, "security": CYBINT, "social": HUMINT,
}

# When neither source nor category resolves, default to HUMINT — the residual bucket
# is human-reported news, which is what an unclassified free-text event usually is.
DEFAULT_DISCIPLINE = HUMINT


def discipline_for(source: str | None, category: str | None) -> str:
    """Deterministically map an event to its intelligence discipline.

    Source provenance wins (a USGS/CISA/OpenSanctions feed is unambiguous); else
    the category (matched case-insensitively across both category vocabularies);
    else DEFAULT_DISCIPLINE. Never raises — always returns a valid discipline.
    """
    if source:
        d = SOURCE_DISCIPLINE.get(source.strip().lower())
        if d:
            return d
    if category:
        d = CATEGORY_DISCIPLINE.get(category.strip().lower())
        if d:
            return d
    return DEFAULT_DISCIPLINE
