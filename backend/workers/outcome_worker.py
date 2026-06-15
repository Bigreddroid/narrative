"""
STEP 10 — OUTCOME EVALUATION (real, evidence-grounded).

Replaces the old status-heuristic placeholder. For each elapsed prediction it
gathers evidence that emerged AFTER the prediction was made (later articles for
the same event) and asks the model to judge whether the prediction actually
materialized — grounded in that later evidence, never in the original sources.

Honest by design: if no post-prediction evidence exists yet, the outcome is
"too_early" with NO calibration score (we never fabricate a result).

Calibration uses a Brier score: p = prediction_score/100 treated as the stated
probability; actual o = {materialized:1.0, partial:0.5, failed:0.0};
calibration_error = (p - o)^2. too_early -> calibration_error left NULL.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

import anthropic

from backend.config import get_settings
from backend.database import AsyncSessionLocal
from backend.models.article import Article
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.narrative_event import NarrativeEvent
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.prediction_outcome import PredictionOutcome

logger = logging.getLogger(__name__)
settings = get_settings()

# Only evaluate predictions old enough that a short-horizon claim could resolve.
MIN_AGE_DAYS = 5
MAX_PER_RUN = 50

_OUTCOME_TO_SCORE = {"materialized": 1.0, "partial": 0.5, "failed": 0.0}

JUDGE_SYSTEM = """You are the outcome evaluator for The Narrative.
You are given a PREDICTION made on a past date, and LATER EVIDENCE that emerged
after that date. Judge ONLY against the later evidence whether the prediction
came true. Do not reward vague predictions. Be strict and honest.

Return valid JSON only, no markdown:
{
  "outcome": "materialized" | "partial" | "failed" | "too_early",
  "justification": "1-3 sentences citing the later evidence",
  "key_evidence": "the strongest later-evidence sentence"
}
Use "too_early" only if the later evidence genuinely cannot resolve the claim."""


def _brier(prediction_score: int | None, outcome: str) -> float | None:
    if outcome not in _OUTCOME_TO_SCORE or prediction_score is None:
        return None
    p = max(0.0, min(1.0, prediction_score / 100.0))
    return round((p - _OUTCOME_TO_SCORE[outcome]) ** 2, 4)


def _judge(prediction_reasoning: str, impact: str, evidence_block: str) -> dict:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    user = (
        f"PREDICTION (made earlier):\n{prediction_reasoning}\n\n"
        f"PREDICTED IMPACT:\n{impact}\n\n"
        f"LATER EVIDENCE (emerged after the prediction):\n{evidence_block}"
    )
    resp = client.messages.create(
        model=settings.consequence_engine_model,
        max_tokens=512,
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    return json.loads(resp.content[0].text.strip())


async def run_outcome_worker() -> dict:
    start = time.perf_counter()
    evaluated = pending = errors = 0

    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=MIN_AGE_DAYS)
        rows = (await db.execute(
            select(EventConsequenceMap, NarrativeEvent)
            .join(NarrativeEvent, EventConsequenceMap.narrative_event_id == NarrativeEvent.id)
            .where(EventConsequenceMap.prediction_score.isnot(None))
            .where(NarrativeEvent.first_detected_at < cutoff)
            .where(~EventConsequenceMap.narrative_event_id.in_(
                select(PredictionOutcome.narrative_event_id).where(PredictionOutcome.evaluated_at.isnot(None))
            ))
            .order_by(EventConsequenceMap.prediction_score.desc())
            .limit(MAX_PER_RUN)
        )).all()

        for cmap, event in rows:
            try:
                # Gather evidence that emerged AFTER the prediction was made.
                later = (await db.execute(
                    select(Article)
                    .where(Article.narrative_event_id == event.id)
                    .where(Article.published_at > cmap.created_at)
                    .order_by(Article.published_at.desc())
                    .limit(8)
                )).scalars().all()

                if not later:
                    db.add(PredictionOutcome(
                        id=uuid.uuid4(),
                        narrative_event_id=event.id,
                        original_prediction_score=cmap.prediction_score,
                        predicted_timeline=(cmap.direct_impact or {}).get("timeline") if isinstance(cmap.direct_impact, dict) else None,
                        actual_outcome="too_early",
                        outcome_notes="No post-prediction evidence available yet.",
                        evaluated_at=datetime.now(timezone.utc),
                        calibration_error=None,
                    ))
                    pending += 1
                    continue

                evidence_block = "\n".join(
                    f"- [{a.published_at:%Y-%m-%d}] {a.title}: {(a.content or '')[:300]}" for a in later
                )
                impact = json.dumps(cmap.direct_impact, ensure_ascii=False) if cmap.direct_impact else ""
                verdict = _judge(cmap.prediction_reasoning or event.canonical_title, impact, evidence_block)
                outcome = verdict.get("outcome", "too_early")

                db.add(PredictionOutcome(
                    id=uuid.uuid4(),
                    narrative_event_id=event.id,
                    original_prediction_score=cmap.prediction_score,
                    predicted_timeline=(cmap.direct_impact or {}).get("timeline") if isinstance(cmap.direct_impact, dict) else None,
                    actual_outcome=outcome,
                    outcome_notes=f"{verdict.get('justification','')} | evidence: {verdict.get('key_evidence','')}",
                    evaluated_at=datetime.now(timezone.utc),
                    calibration_error=_brier(cmap.prediction_score, outcome),
                ))
                evaluated += 1
            except Exception as exc:
                logger.error("Outcome eval error for event %s: %s", event.id, exc)
                errors += 1

        db.add(PipelineMetric(
            id=uuid.uuid4(),
            worker_name="outcome_worker",
            errors=errors,
            duration_seconds=round(time.perf_counter() - start, 2),
        ))
        await db.commit()

    logger.info("Outcome worker: evaluated=%d pending=%d errors=%d", evaluated, pending, errors)
    return {"evaluated": evaluated, "pending": pending, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_outcome_worker())
