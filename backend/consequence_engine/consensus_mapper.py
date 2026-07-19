"""
Consequence mapping engine.
ONE LLM call per cluster. Never per article.
Routed through backend.services.llm — free/local (Ollama) by default, or the
opt-in paid provider (~$0.003-0.015 per call). Callers gate paid calls via
cost_guard and degrade to storing the raw cluster when no LLM is available.
"""

import json
import logging
import time
from typing import Any

from backend.config import get_settings
from backend.services import llm

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are the consequence mapping engine for The Narrative — \
world consequence intelligence infrastructure.

Your job is not to summarize news.
Your job is to map causal chains from world events to \
citizen-level consequences with evidence at every node.

You receive a cluster of articles from multiple sources \
covering the same real-world event. You must:

1. Identify consensus — what all sources agree on
2. Identify disputes — where sources contradict
3. Build a causal chain grounded in evidence only
4. Label every node:
   VERIFIED FACT | INFERRED MECHANISM | SPECULATIVE EFFECT
5. Extract exact evidence sentences per node
6. Be specific — numbers and timelines where evidence exists

Precision rules:
'Prices may rise' → NOT acceptable
'LPG prices likely up 12-18% within 6 weeks based on \
reduced tanker throughput' → acceptable

Return valid JSON only.
No preamble. No markdown. No backticks.
Never invent causal steps without evidence.
Never omit uncertainty."""

DEEP_USER_TEMPLATE = """Map the full consequence chain for this event cluster.

EVENT CLUSTER ({article_count} sources):
{articles_block}

USER CONTEXT: Citizens in {country}.

Return this exact JSON:
{{
  "canonical_title": "neutral definitive title",
  "canonical_summary": "2 sentences max",
  "consensus": "what all sources agree on",
  "disputed": ["disputed points"],
  "geo_centroid": {{
    "lat": 0.0,
    "lng": 0.0,
    "region": "primary affected region name"
  }},
  "consequence_chain": [
    {{
      "step": 1,
      "node": "chain node name",
      "description": "specific, numbers if available",
      "type": "VERIFIED FACT|INFERRED MECHANISM|SPECULATIVE EFFECT",
      "evidence": "exact sentence from source",
      "source": "source name",
      "actors": ["who is involved"]
    }}
  ],
  "direct_impact": {{
    "description": "specific citizen effect",
    "timeline": "X days|weeks|months",
    "severity": "low|medium|high|critical",
    "type": "VERIFIED FACT|INFERRED MECHANISM|SPECULATIVE EFFECT",
    "evidence": "supporting sentence + source",
    "affected_groups": ["who feels this most"]
  }},
  "indirect_impact": {{
    "description": "slower downstream consequence",
    "timeline": "X weeks|months|years",
    "severity": "low|medium|high|critical",
    "type": "VERIFIED FACT|INFERRED MECHANISM|SPECULATIVE EFFECT",
    "evidence": "supporting sentence + source",
    "affected_groups": ["who feels this downstream"]
  }},
  "prediction_score": 0,
  "prediction_reasoning": "2 sentences",
  "confidence": "low|medium|high",
  "category": "geopolitics|economy|climate|health|technology|conflict|policy",
  "current_status": "developing|stable|resolved|escalating",
  "global_importance_score": 0,
  "affected_sectors": [],
  "affected_professions": [],
  "geographic_relevance": [],
  "follow_keywords": []
}}"""

LIGHT_USER_TEMPLATE = """Summarize this event cluster and its basic citizen impact.

EVENT CLUSTER ({article_count} sources):
{articles_block}

Return this exact JSON:
{{
  "canonical_title": "neutral definitive title",
  "canonical_summary": "2 sentences max",
  "consensus": "what all sources agree on",
  "disputed": [],
  "geo_centroid": {{
    "lat": 0.0,
    "lng": 0.0,
    "region": "primary affected region name"
  }},
  "consequence_chain": [],
  "direct_impact": {{
    "description": "basic citizen effect",
    "timeline": "unknown",
    "severity": "low|medium|high|critical",
    "type": "INFERRED MECHANISM",
    "evidence": "",
    "affected_groups": []
  }},
  "indirect_impact": null,
  "prediction_score": 0,
  "prediction_reasoning": "",
  "confidence": "low",
  "category": "geopolitics|economy|climate|health|technology|conflict|policy",
  "current_status": "developing|stable|resolved|escalating",
  "global_importance_score": 0,
  "affected_sectors": [],
  "affected_professions": [],
  "geographic_relevance": [],
  "follow_keywords": []
}}"""


# Drift guard: the category enum the LLM is told to pick from lives (as the
# canonical list) in backend/taxonomy.py LLM_CATEGORIES. Assert the templates still
# match it so the two can't silently diverge. Zero runtime cost beyond import.
from backend import taxonomy as _taxonomy  # noqa: E402
_LLM_CAT_ENUM = "|".join(_taxonomy.LLM_CATEGORIES)
assert f'"category": "{_LLM_CAT_ENUM}"' in DEEP_USER_TEMPLATE, (
    "consensus_mapper DEEP template category enum drifted from taxonomy.LLM_CATEGORIES"
)
assert f'"category": "{_LLM_CAT_ENUM}"' in LIGHT_USER_TEMPLATE, (
    "consensus_mapper LIGHT template category enum drifted from taxonomy.LLM_CATEGORIES"
)


def _build_articles_block(articles: list[dict]) -> str:
    lines = []
    for article in articles:
        content_preview = (article.get("content") or "")[:2000]
        lines.append(
            f"SOURCE: {article.get('source_name', 'Unknown')} "
            f"[{article.get('bias_rating', 'unknown')}]\n"
            f"TITLE: {article.get('title', '')}\n"
            f"CONTENT: {content_preview}\n---"
        )
    return "\n".join(lines)


def map_cluster(
    articles: list[dict],
    depth: str,
    country: str = "global",
) -> dict[str, Any]:
    """
    Call Claude once to map the consequence chain for a cluster.
    Sync so callers can safely offload to asyncio.to_thread().

    Args:
        articles: list of dicts with keys: title, content, source_name, bias_rating
        depth: "deep" | "light"
        country: user context country for consequence framing

    Returns:
        Parsed consequence map dict + metadata (tokens, cost, duration)
    """
    if not articles:
        raise ValueError("No articles provided to map_cluster")

    articles_block = _build_articles_block(articles)

    if depth == "deep":
        user_msg = DEEP_USER_TEMPLATE.format(
            article_count=len(articles),
            articles_block=articles_block,
            country=country,
        )
    else:
        user_msg = LIGHT_USER_TEMPLATE.format(
            article_count=len(articles),
            articles_block=articles_block,
        )

    start = time.perf_counter()
    result = llm.complete(
        system=SYSTEM_PROMPT,
        user=user_msg,
        max_tokens=4096,
        json_mode=True,
    )
    duration = time.perf_counter() - start

    raw_text = result.text
    input_tokens = result.input_tokens
    output_tokens = result.output_tokens
    cost_usd = result.cost_usd

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON: %s\nRaw: %.200s", exc, raw_text)
        raise ValueError(f"LLM returned non-JSON response: {exc}") from exc

    parsed["_meta"] = {
        "provider": result.provider,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "duration_seconds": round(duration, 2),
        "depth": depth,
        "article_count": len(articles),
    }

    logger.info(
        "Mapping complete (%s): depth=%s articles=%d tokens=%d cost=$%.4f",
        result.provider,
        depth,
        len(articles),
        input_tokens + output_tokens,
        cost_usd,
    )

    return parsed


# ── Binary forecasting (external-benchmark path) ───────────────────────────────
# Deliberately separate from map_cluster: the benchmark harness needs the engine's
# reasoning core to answer an arbitrary yes/no question with ONE auditable
# probability, not a full consequence map. Reuses the same llm.complete plumbing.
BINARY_FORECAST_SYSTEM = """You are a calibrated probabilistic forecaster.
Given a yes/no question and its background, output your probability that the
answer resolves YES. Be well-calibrated: use the full 0-100 range, avoid false
confidence, and reflect genuine uncertainty. Return valid JSON only. No preamble,
no markdown, no backticks."""

BINARY_FORECAST_USER = """QUESTION: {question}

BACKGROUND: {background}

Return this exact JSON:
{{
  "probability": <integer 0-100, your probability the answer is YES>,
  "reasoning": "1-2 sentences of the key drivers"
}}"""


def forecast_binary(question_text: str, background: str = "") -> dict:
    """Ask the engine's reasoning core a single yes/no question.

    Returns {"probability": int 0-100, "reasoning": str, "_meta": {...}}. Raises
    ValueError if the model returns unparseable JSON or no usable probability, so
    the harness can skip the item rather than score a garbage forecast.
    """
    user = BINARY_FORECAST_USER.format(
        question=question_text.strip(),
        background=(background or "").strip() or "(none provided)",
    )
    result = llm.complete(system=BINARY_FORECAST_SYSTEM, user=user, max_tokens=512, json_mode=True)

    raw = result.text
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Reuse the shared salvage path if present (truncated/wrapped JSON).
        cleaner = getattr(llm, "clean_json", None) or getattr(llm, "salvage_truncated_json", None)
        if cleaner is None:
            raise ValueError(f"binary forecast returned non-JSON: {raw[:200]}")
        parsed = cleaner(raw)
        if not isinstance(parsed, dict):
            raise ValueError(f"binary forecast returned non-JSON: {raw[:200]}")

    p = parsed.get("probability")
    try:
        p = float(p)
    except (TypeError, ValueError):
        raise ValueError(f"binary forecast missing numeric probability: {parsed!r}")
    # Tolerate a 0-1 fraction OR a 0-100 percent; normalize to an int 0-100.
    if 0.0 <= p <= 1.0:
        p *= 100.0
    p = max(0, min(100, int(round(p))))

    return {
        "probability": p,
        "reasoning": str(parsed.get("reasoning", "")).strip(),
        "_meta": {
            "provider": result.provider,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": result.cost_usd,
        },
    }
