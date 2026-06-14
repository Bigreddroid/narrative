"""
LEAN rules-based importance (0-100) for terminal feed ranking.
Heavy AI routing / deep prediction is stretch.
Keep simple global_importance_score + basic tiers.
"""

import re

CROSS_SOURCE_COVERAGE_THRESHOLD = 3
TIER_1_SOURCES = {
    "reuters",
    "associated press",
    "financial times",
    "bloomberg",
    "bbc news",
    "the economist",
}

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


def score_article(title: str, content: str, source_name: str) -> float:
    text = f"{title} {content}"
    score = 0.0

    if AFFECTED_POPULATION_KEYWORDS.search(text):
        score += 15
    if ECONOMIC_KEYWORDS.search(text):
        score += 15
    if STATE_ACTOR_KEYWORDS.search(text):
        score += 15
    if CONFLICT_KEYWORDS.search(text):
        score += 10
    if COMMODITY_KEYWORDS.search(text):
        score += 10

    if source_name.lower() in TIER_1_SOURCES:
        score += 15

    return min(score, 100.0)


def score_cluster(articles: list[dict]) -> float:
    if not articles:
        return 0.0

    source_names = {a.get("source_name", "").lower() for a in articles}
    avg_score = sum(a.get("article_score", 0.0) for a in articles) / len(articles)

    bonus = 0.0
    if len(source_names) >= CROSS_SOURCE_COVERAGE_THRESHOLD:
        bonus += 20

    if source_names & TIER_1_SOURCES:
        bonus += 15

    return min(avg_score + bonus, 100.0)


def get_mapping_depth(cluster_score: float, importance_threshold_deep: int, importance_threshold_light: int) -> str:
    if cluster_score >= importance_threshold_deep:
        return "deep"
    if cluster_score >= importance_threshold_light:
        return "light"
    return "none"
