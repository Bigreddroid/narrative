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

from backend.database import AsyncSessionLocal
from backend.models.narrative_event import NarrativeEvent
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.prediction_outcome import PredictionOutcome

logger = logging.getLogger(__name__)

EVALUATION_LOOKBACK_DAYS = 30


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
                # Heuristic outcome evaluation based on current event status
                if event.current_status == "resolved":
                    actual_outcome = "materialized"
                    calibration_error = abs(prediction_score - 85) / 100.0
                elif event.current_status == "escalating":
                    actual_outcome = "partial"
                    calibration_error = abs(prediction_score - 65) / 100.0
                elif event.current_status == "stable":
                    actual_outcome = "failed"
                    calibration_error = prediction_score / 100.0
                else:
                    actual_outcome = "pending"
                    calibration_error = 0.0

                outcome = PredictionOutcome(
                    id=uuid.uuid4(),
                    narrative_event_id=event_id,
                    original_prediction_score=prediction_score,
                    predicted_timeline="30 days",
                    actual_outcome=actual_outcome,
                    outcome_notes=f"Auto-evaluated based on event status: {event.current_status}",
                    evaluated_at=datetime.now(timezone.utc),
                    calibration_error=calibration_error,
                )
                db.add(outcome)
                evaluated += 1

            except Exception as exc:
                logger.error("Outcome eval error for event %s: %s", event_id, exc)
                errors += 1

        await db.commit()

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
