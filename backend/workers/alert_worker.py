"""
STEP 9 — ALERTS (every 30 minutes)
Matches user_follows to new/revised events.
Sends FCM push notifications.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from backend.config import get_settings
from backend.database import AsyncSessionLocal
from backend.models.narrative_event import NarrativeEvent
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.user import Notification, User, UserFollow

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_fcm_app():
    import firebase_admin
    from firebase_admin import credentials

    if not firebase_admin._apps:
        if settings.firebase_service_account_json:
            import tempfile, os
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                f.write(settings.firebase_service_account_json)
                cred_path = f.name
            cred = credentials.Certificate(cred_path)
            os.unlink(cred_path)
        else:
            cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)

    return firebase_admin.get_app()


async def send_fcm_notification(fcm_token: str, title: str, body: str, data: dict) -> bool:
    try:
        from firebase_admin import messaging
        _get_fcm_app()
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in data.items()},
            token=fcm_token,
        )
        messaging.send(message)
        return True
    except Exception as exc:
        logger.warning("FCM send failed: %s", exc)
        return False


async def run_alert_worker() -> dict:
    start = time.perf_counter()
    alerts_sent = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        # Find recently updated events (last 35 minutes to overlap with 30-min interval)
        from sqlalchemy import text
        recent_events_result = await db.execute(
            text("""
                SELECT id FROM narrative_events
                WHERE last_updated_at > NOW() - INTERVAL '35 minutes'
                  AND is_mapped = TRUE
            """)
        )
        recent_event_ids = [row[0] for row in recent_events_result]

        if not recent_event_ids:
            logger.info("Alert worker: no recent events")
            return {"alerts_sent": 0, "errors": 0}

        for event_id in recent_event_ids:
            event = await db.get(NarrativeEvent, event_id)
            if not event:
                continue

            follows_result = await db.execute(
                select(UserFollow)
                .where(UserFollow.narrative_event_id == event_id)
                .where(UserFollow.is_active == True)
            )
            follows = follows_result.scalars().all()

            for follow in follows:
                user = await db.get(User, follow.user_id)
                if not user or not user.fcm_token:
                    continue

                # Paid users only get push alerts
                if user.tier == "free":
                    continue

                try:
                    payload = {
                        "event_id": str(event_id),
                        "prediction_score": str(event.consequence_maps[0].prediction_score if event.consequence_maps else 0),
                        "status": event.current_status,
                    }
                    sent = await send_fcm_notification(
                        user.fcm_token,
                        f"Consequence update: {event.canonical_title[:60]}",
                        f"Status: {event.current_status}. Tap to see the chain.",
                        payload,
                    )
                    if sent:
                        notification = Notification(
                            id=uuid.uuid4(),
                            user_id=user.id,
                            narrative_event_id=event_id,
                            type="event_update",
                            payload=payload,
                            sent_at=datetime.now(timezone.utc),
                        )
                        db.add(notification)
                        alerts_sent += 1
                except Exception as exc:
                    logger.error("Alert error for user %s: %s", user.id, exc)
                    errors += 1

        await db.commit()

        duration = time.perf_counter() - start
        metric = PipelineMetric(
            id=uuid.uuid4(),
            worker_name="alert_worker",
            alerts_sent=alerts_sent,
            errors=errors,
            duration_seconds=round(duration, 2),
        )
        db.add(metric)
        await db.commit()

    logger.info(
        "Alert worker done: sent=%d errors=%d duration=%.1fs",
        alerts_sent,
        errors,
        time.perf_counter() - start,
    )
    return {"alerts_sent": alerts_sent, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_alert_worker())
