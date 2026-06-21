"""
Claude consequence mapping engine.
ONE call per cluster. Never per article.
Costs ~$0.003-0.015 per call depending on depth.
"""

import json
import logging
import time
from typing import Any

import anthropic

from backend.config import get_settings

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


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    # claude-sonnet-4-20250514 pricing: $3/MTok in, $15/MTok out
    return (input_tokens * 3 + output_tokens * 15) / 1_000_000


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

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    start = time.perf_counter()
    response = client.messages.create(
        model=settings.consequence_engine_model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    duration = time.perf_counter() - start

    raw_text = response.content[0].text.strip()
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_usd = _estimate_cost(input_tokens, output_tokens)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("Claude returned invalid JSON: %s\nRaw: %.200s", exc, raw_text)
        raise ValueError(f"Claude returned non-JSON response: {exc}") from exc

    parsed["_meta"] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "duration_seconds": round(duration, 2),
        "depth": depth,
        "article_count": len(articles),
    }

    logger.info(
        "Claude mapping complete: depth=%s articles=%d tokens=%d cost=$%.4f",
        depth,
        len(articles),
        input_tokens + output_tokens,
        cost_usd,
    )

    return parsed
