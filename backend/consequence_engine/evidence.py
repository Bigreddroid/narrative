"""
Can we back this event up? One rule, applied by every route that serves events.

This lived inside ``routes/events.py`` and was applied to exactly one of the four
read paths. The one it missed mattered most: ``routes/exposure.py`` ranks by
importance and produces the deck's headline exposure number, and severed events
skew high-importance — measured on the live corpus, **190 of the exposure model's
top 200 events (95%) were severed**, versus 9 genuinely sourced. Quarantining the
list feed while the scored model stayed contaminated fixed the symptom nobody
reads. Hence a shared module: a filter that only some callers apply is not a
filter.

Three states, and the middle one is why a blanket "hide events with no outlets"
filter would be wrong:

    sourced        >=1 distinct outlet carries this story
    official_feed  nws/usgs/gdacs/cisa/nhc/launchlibrary/open-meteo/imint and the
                   demo seeds publish structured records, not prose. No article is
                   CORRECT — the issuing agency IS the source. Blanket-filtering
                   would delete every earthquake, storm and CISA advisory.
    severed        an article-derived event whose articles are gone. A DEFECT — the
                   cluster_worker outage (2026-07-13..25) left 4,036 of these.
"""

from urllib.parse import urlparse

from sqlalchemy import exists, or_

from backend.models.article import Article
from backend.models.narrative_event import NarrativeEvent

# A publisher can reach us under several feed labels — "Deutsche Welle" and
# "Deutsche Welle — Business" are two configured feeds, one newsroom. Counting
# outlet NAMES made that one publisher look like two independent sources agreeing,
# which is manufactured corroboration: measured on the live corpus, 19 events
# carried the same publisher twice (14 of them Deutsche Welle), and corroboration
# is what raises the Admiralty credibility digit and clears the two-source gate.
#
# Deliberately NOT a curated alias table — that would need editing every time a feed
# is added, and would silently under-count whatever nobody remembered to list.
_MULTI_PART_TLDS = ("co.uk", "com.au", "co.in", "co.jp", "com.br", "co.za",
                    "com.sg", "com.tr", "co.kr", "com.mx", "co.nz", "com.hk")


def outlet_key(url: str | None, name: str | None) -> str:
    """The identity corroboration should count: one key per PUBLISHER.

    Derived from the article's own address, because that is a fact about the
    document rather than a label we chose: every article on dw.com is Deutsche
    Welle no matter which feed carried it. Falls back to the outlet name when there
    is no usable host (structured feeds publish records, not links), so a source is
    never silently merged into another just because its URL is missing.
    """
    host = ""
    if url:
        try:
            host = (urlparse(url).netloc or "").strip().lower()
        except ValueError:
            host = ""
    if not host or "." not in host:
        return (name or "Unknown").strip().lower() or "unknown"
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    # news.bbc.co.uk and bbc.co.uk are one publisher; keep the registrable domain.
    keep = 3 if any(host.endswith("." + t) for t in _MULTI_PART_TLDS) else 2
    return ".".join(parts[-keep:]) if len(parts) > keep else host


def count_outlets(rows) -> int:
    """Distinct publishers among (url, name) pairs for one event."""
    return len({outlet_key(u, n) for u, n in rows})


def has_article():
    """SQL EXISTS: this event has at least one source article."""
    return exists().where(Article.narrative_event_id == NarrativeEvent.id)


def is_article_derived():
    """SQL: this event came from a path that ALWAYS produces a source article.

    Two such paths: the clusterer (builds an event *from* an article and leaves
    ``source`` NULL) and the ``osint_*`` feeds.

    Expressed as a rule rather than an allowlist of known-good structured feeds,
    so a feed added tomorrow is not misclassified as broken on the day it ships.
    """
    return or_(NarrativeEvent.source.is_(None), NarrativeEvent.source.like("osint_%"))


def evidenced():
    """SQL predicate for 'we can back this up' — the filter routes should apply."""
    return or_(has_article(), ~is_article_derived())


def state(event, source_count: int) -> str:
    """Python mirror of the SQL above, for payload labelling."""
    if source_count > 0:
        return "sourced"
    src = event.source or ""
    if src == "" or src.startswith("osint_"):
        return "severed"
    return "official_feed"
