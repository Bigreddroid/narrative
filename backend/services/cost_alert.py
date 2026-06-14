"""
Sends an admin alert email when daily Claude cost exceeds threshold.
Uses smtplib — no external library needed.
"""

import logging
import smtplib
from email.message import EmailMessage

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def send_cost_alert(daily_cost: float) -> None:
    if not settings.admin_alert_email:
        logger.debug("No admin alert email configured, skipping cost alert")
        return

    subject = f"[The Narrative] Daily Claude cost alert: ${daily_cost:.2f}"
    body = (
        f"Daily Claude API cost has reached ${daily_cost:.2f}, "
        f"exceeding the configured threshold of ${settings.claude_daily_cost_alert_usd:.2f}.\n\n"
        f"Monthly budget: ${settings.claude_monthly_budget_usd:.2f}\n\n"
        f"Review cost breakdown at /admin/costs"
    )

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = "alerts@thenarrative.io"
        msg["To"] = settings.admin_alert_email
        msg.set_content(body)

        smtp_host = settings.smtp_host or "localhost"
        smtp_port = settings.smtp_port or 587
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.ehlo()
            if settings.smtp_user and settings.smtp_password:
                smtp.starttls()
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)

        logger.info("Cost alert email sent to %s (cost=$%.2f)", settings.admin_alert_email, daily_cost)
    except Exception as exc:
        logger.warning("Failed to send cost alert email: %s", exc)


async def check_and_alert_daily_cost(db) -> None:
    from backend.admin.metrics import get_today_metrics
    metrics = await get_today_metrics(db)
    daily_cost = metrics["claude_cost_usd"]

    if daily_cost > settings.claude_daily_cost_alert_usd:
        send_cost_alert(daily_cost)
