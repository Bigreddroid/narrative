"""
Title-based near-duplicate detection for directly-created events (GDELT/OSINT,
hazard feeds). The pgvector clusterer only runs on the *articles* pipeline; these
events are upserted straight into narrative_events keyed by (source, external_id),
so a dozen GDELT docs about the same story each spawn their own event.

This module decides "same story?" cheaply and deterministically — no AI, no
embeddings — from the canonical title (token-set Jaccard with light stemming +
stopword removal) gated by category and reinforced by geography overlap. Pure
functions so the thresholds are unit-testable.
"""

import re

# Filler that carries no story identity — dropped before comparison.
_STOPWORDS = frozenset({
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "but",
    "with", "from", "by", "as", "after", "before", "amid", "over", "into",
    "against", "following", "near", "its", "their", "his", "her", "out",
    "is", "are", "was", "were", "be", "been", "has", "have", "had", "will",
    "that", "this", "these", "those", "it", "they", "he", "she", "new",
    "report", "reports", "reported", "says", "say", "said", "update", "live",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _stem(tok: str) -> str:
    """Strip a trailing plural/3rd-person 's' so strikes≈strike, missiles≈missile,
    states≈state. Deliberately conservative — stripping 'es'/'ed' mangles singular
    forms (missile→missil), so we don't."""
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def normalize_tokens(text: str | None) -> frozenset[str]:
    """Title → significant stemmed token set (lowercased, punctuation/stopwords out).

    Periods are dropped first so abbreviations match their bare form
    (U.S.→us, U.K.→uk)."""
    if not text:
        return frozenset()
    toks = _TOKEN_RE.findall(text.lower().replace(".", ""))
    return frozenset(_stem(t) for t in toks if t not in _STOPWORDS and len(t) > 1)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / len(a | b) if inter else 0.0


def _geo_overlap(geo_a, geo_b) -> bool:
    """Any shared place token between two geography lists (case-insensitive)."""
    ta = {w for g in (geo_a or []) for w in _TOKEN_RE.findall(str(g).lower())}
    tb = {w for g in (geo_b or []) for w in _TOKEN_RE.findall(str(g).lower())}
    return bool(ta & tb)


# Thresholds:
#  TITLE_HIGH  — Jaccard this high merges outright (clearly the same headline).
#  TITLE_MID   — moderate Jaccard merges only with shared geography.
#  CONTAIN     — overlap coefficient (|A∩B| / min(|A|,|B|)); a terse headline whose
#                tokens are nearly contained in a verbose one ("US strikes Iran" vs
#                "U.S. has launched a strike against Iran …") merges when geography
#                also overlaps. Guards length-asymmetry that sinks Jaccard.
TITLE_HIGH = 0.6
TITLE_MID = 0.45
CONTAIN = 0.75
MIN_SHARED = 2  # never merge on a single shared token (usually a generic word)


def title_similarity(title_a: str | None, title_b: str | None) -> float:
    """0..1 token-set Jaccard of two normalized titles."""
    return _jaccard(normalize_tokens(title_a), normalize_tokens(title_b))


def _exact_tokens(text: str | None) -> frozenset[str]:
    """Raw lowercased alphanumeric token set — keeps stopwords, digits AND single
    chars (unlike normalize_tokens). Order and repeats are ignored, but the
    distinguishing bits stay: 'Layer A' vs 'Layer D', 'Tranche 1' vs 'Tranche 2'."""
    return frozenset(_TOKEN_RE.findall(text.lower())) if text else frozenset()


def same_story_exact(title_a: str | None, title_b: str | None) -> bool:
    """Identical titles up to order/repeats/punctuation. Safe for structured feeds:
    'Earthquake — Earthquake in Venezuela' == 'Earthquake in Venezuela', but distinct
    quakes ('M4.6 … Palu' vs 'M4.5 … Tobelo') and distinct launches ('Layer A' vs
    'Layer D') keep their identifier tokens and stay separate."""
    a = _exact_tokens(title_a)
    return bool(a) and a == _exact_tokens(title_b)


def is_duplicate(
    title_a: str | None,
    title_b: str | None,
    geo_a=None,
    geo_b=None,
    *,
    title_high: float = TITLE_HIGH,
    title_mid: float = TITLE_MID,
    contain: float = CONTAIN,
) -> bool:
    """True if two events look like the same story.

    Caller MUST pre-restrict to the same category — this only weighs title +
    geography. A strong title match merges outright; otherwise containment or a
    moderate match merges only with a shared place, so distinct same-shape
    headlines ("US strikes Iran" vs "US strikes Iraq") stay separate.
    """
    ta, tb = normalize_tokens(title_a), normalize_tokens(title_b)
    inter = len(ta & tb)
    if inter < MIN_SHARED:
        return False
    jac = inter / len(ta | tb)
    if jac >= title_high:
        return True
    # Below the strong bar, require both a shared place AND near-containment. A
    # plain "moderate Jaccard + geo" rule wrongly merges same-place / same-shape but
    # different-action headlines ("US strikes Iran" vs "US sanctions Iran", which
    # share {us, iran} + geo); containment demands the smaller title be mostly a
    # subset of the larger, which those fail.
    overlap_coeff = inter / min(len(ta), len(tb))
    if overlap_coeff >= contain and _geo_overlap(geo_a, geo_b):
        return True
    return False
