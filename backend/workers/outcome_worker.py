"""
STEP 10 — OUTCOME EVALUATION (every 7 days), real + evidence-grounded.

For each elapsed, confident prediction we gather evidence that emerged AFTER the
prediction was made (later articles for the same event) and ask the model to
judge whether the prediction actually materialized — grounded ONLY in that later
evidence, never the original sources. This replaces the old status-heuristic
(which derived the outcome circularly from event.current_status and proved
nothing).

Honest by design: if no post-prediction evidence exists yet, we SKIP the event
(no row written) so it is re-evaluated in a later run once evidence accrues —
we never fabricate a result.

Calibration: p = prediction_score/100 is the stated probability; the realised
outcome o = {materialized:1.0, partial:0.5, failed:0.0}. Brier/log-loss/ECE are
computed over the accumulated (p, o) pairs.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta

import anthropic
from sqlalchemy import select

from backend.config import get_settings
from backend.consequence_engine import calibration
from backend.database import AsyncSessionLocal
from backend.models.article import Article
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.narrative_event import NarrativeEvent
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.prediction_outcome import PredictionOutcome

logger = logging.getLogger(__name__)
settings = get_settings()

EVALUATION_LOOKBACK_DAYS = 30          # prediction must be at least this old to grade
MIN_PREDICTION_SCORE = 60              # only grade confident predictions (cost control)
MAX_PER_RUN = 100
MAX_EVIDENCE_ARTICLES = 8

# Realised-outcome → probability the prediction was correct.
_OUTCOME_TO_PROB = {"materialized": 1.0, "partial": 0.5, "failed": 0.0}

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


def _judge(prediction_reasoning: str, impact: str, evidence_block: str) -> dict:
    """Ask the model to grade one prediction against post-prediction evidence."""
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
    text = resp.content[0].text.strip()
    if text.startswith("```"):  # defensive: strip accidental markdown fences
        text = text.strip("`")
        text = text[text.find("{"):]
    return json.loads(text)


async def _historical_pairs(db) -> list[tuple[float, float]]:
    """All evaluated (predicted_probability, observed_outcome) pairs — the calibration set."""
    rows = (await db.execute(
        select(PredictionOutcome.original_prediction_score, PredictionOutcome.observed_probability)
        .where(PredictionOutcome.observed_probability.isnot(None))
        .where(PredictionOutcome.original_prediction_score.isnot(None))
    )).all()
    return [(s / 100.0, o) for s, o in rows]


async def _pattern_records(db) -> list[dict]:
    """Evaluated outcomes tagged with their event category — for pattern base rates."""
    rows = (await db.execute(
        select(NarrativeEvent.category, PredictionOutcome.observed_probability)
        .join(PredictionOutcome, PredictionOutcome.narrative_event_id == NarrativeEvent.id)
        .where(PredictionOutcome.observed_probability.isnot(None))
    )).all()
    return [{"pattern": c or "_all", "outcome": o} for c, o in rows]


async def current_calibrator(db) -> dict:
    """Isotonic recalibration map fit from the accumulated outcomes (identity until enough data)."""
    return calibration.fit_isotonic(await _historical_pairs(db))


async def run_outcome_worker() -> dict:
    start = time.perf_counter()
    evaluated = pending = errors = 0

    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=EVALUATION_LOOKBACK_DAYS)

        rows = (await db.execute(
            select(EventConsequenceMap, NarrativeEvent)
            .join(NarrativeEvent, EventConsequenceMap.narrative_event_id == NarrativeEvent.id)
            .where(EventConsequenceMap.prediction_score.isnot(None))
            .where(EventConsequenceMap.prediction_score >= MIN_PREDICTION_SCORE)
            .where(NarrativeEvent.first_detected_at < cutoff)
            .where(~EventConsequenceMap.narrative_event_id.in_(
                select(PredictionOutcome.narrative_event_id).where(PredictionOutcome.evaluated_at.isnot(None))
            ))
            .order_by(EventConsequenceMap.prediction_score.desc())
            .limit(MAX_PER_RUN)
        )).all()

        for cmap, event in rows:
            try:
                # Evidence that emerged AFTER the prediction was made.
                later = (await db.execute(
                    select(Article)
                    .where(Article.narrative_event_id == event.id)
                    .where(Article.published_at > cmap.created_at)
                    .order_by(Article.published_at.desc())
                    .limit(MAX_EVIDENCE_ARTICLES)
                )).scalars().all()

                if not later:
                    # No post-prediction evidence yet — skip (no row) so a later
                    # run re-evaluates once evidence exists. Never fabricate.
                    pending += 1
                    continue

                evidence_block = "\n".join(
                    f"- [{a.published_at:%Y-%m-%d}] {a.title}: {(a.content or '')[:300]}"
                    for a in later
                )
                impact = json.dumps(cmap.direct_impact, ensure_ascii=False) if cmap.direct_impact else ""
                verdict = _judge(cmap.prediction_reasoning or event.canonical_title, impact, evidence_block)
                outcome = verdict.get("outcome", "too_early")

                if outcome == "too_early":
                    # Genuinely unresolvable on current evidence — retry later.
                    pending += 1
                    continue

                obs = _OUTCOME_TO_PROB.get(outcome)
                if obs is None:
                    pending += 1
                    continue  # unknown label from the judge — don't record

                p = (cmap.prediction_score or 0) / 100.0
                timeline = cmap.direct_impact.get("timeline") if isinstance(cmap.direct_impact, dict) else None
                db.add(PredictionOutcome(
                    id=uuid.uuid4(),
                    narrative_event_id=event.id,
                    original_prediction_score=cmap.prediction_score,
                    predicted_timeline=timeline,
                    actual_outcome=outcome,
                    outcome_label=obs,
                    observed_probability=obs,
                    brier_score=calibration.brier_score(p, obs),
                    log_loss=calibration.log_loss(p, obs),
                    calibration_error=abs(p - obs),
                    evidence={
                        "key_evidence": verdict.get("key_evidence", ""),
                        "articles": [
                            {"title": a.title, "published_at": a.published_at.isoformat() if a.published_at else None}
                            for a in later
                        ],
                    },
                    outcome_notes=f"{verdict.get('justification', '')} | evidence: {verdict.get('key_evidence', '')}",
                    evaluated_at=datetime.now(timezone.utc),
                ))
                evaluated += 1

            except Exception as exc:
                logger.error("Outcome eval error for event %s: %s", event.id, exc)
                errors += 1

        await db.commit()

        # Global calibration health over the whole accumulated dataset.
        all_pairs = await _historical_pairs(db)
        if all_pairs:
            model = calibration.fit_isotonic(all_pairs)
            logger.info(
                "Calibration: n=%d ECE=%.4f recalibrated=%s",
                len(all_pairs), calibration.ece(all_pairs), bool(model["xs"]),
            )
            records = await _pattern_records(db)
            if records:
                logger.info("Pattern base rates: %s", calibration.base_rates(records))

        db.add(PipelineMetric(
            id=uuid.uuid4(),
            worker_name="outcome_worker",
            errors=errors,
            duration_seconds=round(time.perf_counter() - start, 2),
        ))
        await db.commit()

    logger.info(
        "Outcome worker done: evaluated=%d pending=%d errors=%d duration=%.1fs",
        evaluated, pending, errors, time.perf_counter() - start,
    )
    return {"evaluated": evaluated, "pending": pending, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_outcome_worker())
