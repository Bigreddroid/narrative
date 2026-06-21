"""
STEP 10 — OUTCOME EVALUATION (every 7 days)
Evaluates elapsed predictions.
materialized | partial | failed | pending
Stores calibration_error.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, text

from backend.consequence_engine import calibration
from backend.database import AsyncSessionLocal
from backend.models.narrative_event import NarrativeEvent
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.prediction_outcome import PredictionOutcome

logger = logging.getLogger(__name__)

EVALUATION_LOOKBACK_DAYS = 30
LABEL_TO_OUTCOME = {1.0: "materialized", 0.5: "partial", 0.0: "failed"}


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
    """Isotonic recalibration map fit from the accumulated outcomes (identity until enough data).

    Intended to recalibrate future prediction scores + CPE confidence. Re-fit on demand
    from prediction_outcomes (the dataset is the source of truth — no separate store).
    """
    return calibration.fit_isotonic(await _historical_pairs(db))


async def run_outcome_worker() -> dict:
    start = time.perf_counter()
    evaluated = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=EVALUATION_LOOKBACK_DAYS)

        # Find events with high prediction scores that are old enough to evaluate
        events_result = await db.execute(
            text("""
                SELECT ne.id, ecm.prediction_score, ecm.prediction_reasoning
                FROM narrative_events ne
                JOIN event_consequence_maps ecm ON ecm.narrative_event_id = ne.id
                WHERE ne.first_detected_at < :cutoff
                  AND ecm.prediction_score >= 60
                  AND ne.id NOT IN (
                      SELECT narrative_event_id FROM prediction_outcomes
                      WHERE evaluated_at IS NOT NULL
                  )
                ORDER BY ecm.prediction_score DESC
                LIMIT 100
            """),
            {"cutoff": cutoff},
        )
        rows = events_result.fetchall()

        for row in rows:
            event_id, prediction_score, prediction_reasoning = row
            event = await db.get(NarrativeEvent, event_id)
            if not event:
                continue

            try:
                label = calibration.outcome_label(event.current_status)
                if label is None:
                    continue  # still pending — evaluate in a later run

                p = (prediction_score or 0) / 100.0
                outcome = PredictionOutcome(
                    id=uuid.uuid4(),
                    narrative_event_id=event_id,
                    original_prediction_score=prediction_score,
                    predicted_timeline="30 days",
                    actual_outcome=LABEL_TO_OUTCOME[label],
                    outcome_label=label,
                    observed_probability=label,
                    brier_score=calibration.brier_score(p, label),
                    log_loss=calibration.log_loss(p, label),
                    calibration_error=abs(p - label),
                    evidence={"status": event.current_status},
                    outcome_notes=f"Evaluated from status: {event.current_status}",
                    evaluated_at=datetime.now(timezone.utc),
                )
                db.add(outcome)
                evaluated += 1

            except Exception as exc:
                logger.error("Outcome eval error for event %s: %s", event_id, exc)
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

        duration = time.perf_counter() - start
        metric = PipelineMetric(
            id=uuid.uuid4(),
            worker_name="outcome_worker",
            errors=errors,
            duration_seconds=round(duration, 2),
        )
        db.add(metric)
        await db.commit()

    logger.info(
        "Outcome worker done: evaluated=%d errors=%d duration=%.1fs",
        evaluated,
        errors,
        time.perf_counter() - start,
    )
    return {"evaluated": evaluated, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_outcome_worker())
