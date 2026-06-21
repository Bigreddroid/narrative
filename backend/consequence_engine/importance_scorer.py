"""
Rules-based importance scoring. No AI. 0-100.

Article score (v2): graded thematic signals with diminishing returns, a magnitude
multiplier (a "$40 billion" / "40%" / "2 million" story outranks a passing mention),
a graded source-credibility prior, and recency decay — combined through a saturating
curve so strong articles still differentiate near the top instead of pinning at 100.

Routing after cluster scoring:
  >= deep_threshold   → deep Claude mapping (full chain + evidence + prediction)
  >= light_threshold  → light Claude summary
  <  light_threshold  → store only, no Claude
"""

import math
import re
from collections import Counter

CROSS_SOURCE_COVERAGE_THRESHOLD = 3
TIER_1_SOURCES = {
    "reuters",
    "associated press",
    "financial times",
    "bloomberg",
    "bbc news",
    "the economist",
}

# Graded source-credibility prior (multiplier). Tier-1 = 1.0, unknown = default.
DEFAULT_CREDIBILITY = 0.7
SOURCE_CREDIBILITY = {name: 1.0 for name in TIER_1_SOURCES}
SOURCE_CREDIBILITY.update({
    "the new york times": 0.9,
    "the washington post": 0.88,
    "the guardian": 0.85,
    "politico": 0.82,
    "al jazeera": 0.8,
    "cnn": 0.8,
})

# Scoring constants (tunable — part of the versioned engine params).
TAU_COUNT = 1.5            # diminishing-returns rate on repeated keyword hits
SATURATION_S = 45.0        # final-score saturation constant
MAGNITUDE_ALPHA = 0.12     # weight on log-scaled absolute magnitude
PERCENT_BETA = 0.4         # weight on the largest percentage figure
MAGNITUDE_CAP = 2.2        # ceiling on the magnitude multiplier
RECENCY_HALFLIFE_HOURS = 72.0  # article importance half-life

AFFECTED_POPULATION_KEYWORDS = re.compile(
    r"\b(million|billion|population|citizens|workers|households|communities|"
    r"displaced|refugees|casualties|deaths|injured)\b",
    re.IGNORECASE,
)
ECONOMIC_KEYWORDS = re.compile(
    r"\b(gdp|inflation|recession|market|trade|tariff|sanction|supply chain|"
    r"commodity|oil|gas|grain|wheat|shortage|price spike|currency|debt|"
    r"bankruptcy|default|economic)\b",
    re.IGNORECASE,
)
STATE_ACTOR_KEYWORDS = re.compile(
    r"\b(government|president|prime minister|congress|parliament|minister|"
    r"military|nato|un|united nations|g7|g20|imf|world bank|federal reserve|"
    r"central bank|white house|kremlin|beijing|administration)\b",
    re.IGNORECASE,
)
CONFLICT_KEYWORDS = re.compile(
    r"\b(war|conflict|attack|invasion|missile|airstrike|troops|ceasefire|"
    r"nuclear|weapons|armed|military operation|offensive|siege)\b",
    re.IGNORECASE,
)
COMMODITY_KEYWORDS = re.compile(
    r"\b(oil|gas|lng|lpg|wheat|corn|soy|copper|lithium|rare earth|"
    r"fertilizer|food|energy|fuel)\b",
    re.IGNORECASE,
)

# (name, pattern, weight) — graded thematic dimensions.
DIMENSIONS = [
    ("population", AFFECTED_POPULATION_KEYWORDS, 15.0),
    ("economic", ECONOMIC_KEYWORDS, 15.0),
    ("state_actor", STATE_ACTOR_KEYWORDS, 15.0),
    ("conflict", CONFLICT_KEYWORDS, 10.0),
    ("commodity", COMMODITY_KEYWORDS, 10.0),
]

_SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "mn": 1e6,
          "billion": 1e9, "bn": 1e9, "trillion": 1e12, "tn": 1e12}
_MONEY_RE = re.compile(r"\$\s?(\d[\d,]*\.?\d*)\s*(thousand|million|billion|trillion|k|m|mn|bn|tn)?", re.IGNORECASE)
_SCALED_RE = re.compile(r"(\d[\d,]*\.?\d*)\s*(thousand|million|billion|trillion)\b", re.IGNORECASE)
_PERCENT_RE = re.compile(r"(\d[\d,]*\.?\d*)\s?%")


def credibility_of(source_name: str) -> float:
    return SOURCE_CREDIBILITY.get((source_name or "").lower().strip(), DEFAULT_CREDIBILITY)


def _num(s: str) -> float:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return 0.0


def magnitude_multiplier(text: str) -> float:
    """A story citing large figures matters more. μ ∈ [1, MAGNITUDE_CAP]."""
    best_abs = 0.0
    for m in _MONEY_RE.finditer(text):
        best_abs = max(best_abs, _num(m.group(1)) * _SCALE.get((m.group(2) or "").lower(), 1.0))
    for m in _SCALED_RE.finditer(text):
        best_abs = max(best_abs, _num(m.group(1)) * _SCALE[m.group(2).lower()])
    pct = max((_num(m.group(1)) for m in _PERCENT_RE.finditer(text)), default=0.0)

    mu = 1.0 + MAGNITUDE_ALPHA * math.log10(1 + best_abs) + PERCENT_BETA * min(pct, 100) / 100.0
    return min(mu, MAGNITUDE_CAP)


def recency_factor(age_hours: float | None) -> float:
    if age_hours is None:
        return 1.0
    return 0.5 ** (max(0.0, age_hours) / RECENCY_HALFLIFE_HOURS)


def score_article_explain(title: str, content: str, source_name: str, age_hours: float | None = None) -> dict:
    """Full decomposition behind an article's importance score (for audit/admin)."""
    text = f"{title} {content}"

    signals = {}
    thematic = 0.0
    for name, pattern, weight in DIMENSIONS:
        count = len(pattern.findall(text))
        s = weight * (1 - math.exp(-count / TAU_COUNT)) if count else 0.0
        signals[name] = round(s, 2)
        thematic += s

    mu = magnitude_multiplier(text)
    cred = credibility_of(source_name)
    rec = recency_factor(age_hours)

    raw = thematic * mu * cred * rec
    score = round(100 * (1 - math.exp(-raw / SATURATION_S)), 1)
    return {
        "score": score,
        "thematic": round(thematic, 2),
        "signals": signals,
        "magnitude_mult": round(mu, 3),
        "credibility": cred,
        "recency": round(rec, 3),
    }


def score_article(title: str, content: str, source_name: str, age_hours: float | None = None) -> float:
    return score_article_explain(title, content, source_name, age_hours)["score"]


# Cluster aggregation constants.
ROBUST_MAX_WEIGHT = 0.6    # blend toward the strongest article, not the mean
DIVERSITY_BONUS = 15.0     # max bonus for fully independent source coverage
TIER1_BONUS = 12.0         # max bonus for tier-1 corroboration (graded)
TIER1_KAPPA = 1.5          # diminishing returns on multiple tier-1 sources
VELOCITY_BONUS = 10.0      # max bonus for accelerating coverage


def source_entropy(source_names: list[str]) -> float:
    """Normalised Shannon entropy of the source distribution ∈ [0,1].

    Rewards genuinely independent corroboration; 5 articles from one wire ≈ 0.
    """
    names = [n.lower() for n in source_names if n]
    if len(names) <= 1:
        return 0.0
    counts = Counter(names)
    if len(counts) <= 1:
        return 0.0
    n = len(names)
    h = -sum((c / n) * math.log(c / n) for c in counts.values())
    return h / math.log(len(counts))


def _velocity_bonus(articles: list[dict]) -> float:
    """Bonus when coverage is accelerating (more articles in the last 6h than the prior 6h)."""
    ages = [a["age_hours"] for a in articles if a.get("age_hours") is not None]
    if not ages:
        return 0.0
    recent = sum(1 for x in ages if x <= 6)
    prior = sum(1 for x in ages if 6 < x <= 12)
    velocity = recent / max(1, prior)
    return VELOCITY_BONUS * (1 - math.exp(-max(0.0, velocity - 1)))


def score_cluster(articles: list[dict]) -> float:
    """Cluster importance: robust max/mean blend + source-diversity + velocity."""
    if not articles:
        return 0.0

    scores = [a.get("article_score", 0.0) for a in articles]
    base = ROBUST_MAX_WEIGHT * max(scores) + (1 - ROBUST_MAX_WEIGHT) * (sum(scores) / len(scores))

    base += DIVERSITY_BONUS * source_entropy([a.get("source_name", "") for a in articles])

    n_tier1 = len({a.get("source_name", "").lower() for a in articles} & TIER_1_SOURCES)
    base += TIER1_BONUS * (1 - math.exp(-n_tier1 / TIER1_KAPPA))

    base += _velocity_bonus(articles)

    return round(min(base, 100.0), 1)


def get_mapping_depth(cluster_score: float, importance_threshold_deep: int, importance_threshold_light: int) -> str:
    if cluster_score >= importance_threshold_deep:
        return "deep"
    if cluster_score >= importance_threshold_light:
        return "light"
    return "none"


def plan_routing(scored: list[tuple], deep_threshold: int, light_threshold: int, deep_budget: int) -> dict:
    """Budget-aware routing: rank clusters by score, spend the deep-mapping budget on
    the highest first; clusters that qualify for deep but exceed budget fall back to
    light. Returns {key: "deep" | "light" | "none"}.
    """
    plan: dict = {}
    deep_used = 0
    for key, score in sorted(scored, key=lambda kv: -kv[1]):
        if score >= deep_threshold and deep_used < deep_budget:
            plan[key] = "deep"
            deep_used += 1
        elif score >= light_threshold:
            plan[key] = "light"
        else:
            plan[key] = "none"
    return plan
