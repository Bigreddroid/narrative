"""
mailer — the only path that puts a message in front of a real person by email.

🔴 IT IS OFF BY DEFAULT AND MUST STAY THAT WAY. ``email_send_enabled`` defaults to
False, and ``send()`` refuses before it touches a socket. Three separate facts make
that non-negotiable rather than cautious:

  1. Local Docker AND Railway both run a scheduler (docker-compose.yml,
     railway.toml:34-37). There is no leader election or advisory lock anywhere in
     this repo — the established pattern is a settings boolean checked inside the
     worker (``benchmark_publish_enabled``, config.py:174-180). Without the flag,
     BOTH hosts would email the same real people.
  2. That is strictly worse than the duplicate-ledger case the flag was invented for.
     A divergent audit chain is recoverable; an executive distribution list mailed
     twice by two environments is not.
  3. A developer with SMTP credentials in their .env and a copy of production data is
     one worker tick away from mailing a customer's security team.

So the refusal is explicit, it is reported (the caller writes ``suppressed`` to the
delivery log rather than pretending), and turning it on is a deliberate act.

The send itself runs in a thread. ``cost_alert.py`` calls blocking ``smtplib``
directly from async worker context and stalls the event loop; that is a bug being
lived with, not a precedent. This also does NOT swallow exceptions the way
``cost_alert.py:46-47`` does — a failure returns its reason so it can be recorded.
Nothing about a message that never arrived should be silent.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from backend.config import get_settings

logger = logging.getLogger(__name__)


class SendResult:
    """Why a message did or did not go out.

    ``suppressed`` is not a failure and not a success — it is "we deliberately did
    not send", which the delivery log records as its own status. Collapsing it into
    either of the others makes it impossible to answer "why didn't they get it?".
    """

    def __init__(self, status: str, error: str | None = None):
        self.status = status          # sent | suppressed | failed
        self.error = error

    @property
    def sent(self) -> bool:
        return self.status == "sent"


def _blocking_send(host: str, port: int, user: str, password: str,
                   sender: str, recipient: str, subject: str,
                   text_body: str, html_body: str | None) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        # Opportunistic TLS: a local catcher (MailHog, aiosmtpd) offers no STARTTLS
        # and must still work, while a real provider must never be spoken to in the
        # clear. Asking the server rather than assuming is the only way to get both.
        if smtp.has_extn("starttls"):
            smtp.starttls()
            smtp.ehlo()
        if user and password:
            smtp.login(user, password)
        smtp.send_message(msg)


def preflight() -> SendResult | None:
    """Why sending would be refused right now, or None if it would be attempted.

    Separated so a worker can report its posture ("configured but disabled") without
    composing a message first, and so a test can assert the refusal without SMTP.
    """
    s = get_settings()
    if not s.email_send_enabled:
        return SendResult("suppressed", "Email sending is disabled (EMAIL_SEND_ENABLED=false)")
    if not s.smtp_host:
        # Fail closed rather than defaulting to localhost:587 the way cost_alert does.
        # An unconfigured host silently becoming "localhost" is how mail ends up in a
        # place nobody is looking, reported as a success.
        return SendResult("suppressed", "No SMTP host configured (SMTP_HOST is empty)")
    if not s.email_from_address:
        return SendResult("suppressed", "No sender configured (EMAIL_FROM_ADDRESS is empty)")
    return None


async def send(recipient: str, subject: str, text_body: str,
               html_body: str | None = None) -> SendResult:
    refusal = preflight()
    if refusal is not None:
        logger.info("Email to %s not sent: %s", recipient, refusal.error)
        return refusal

    s = get_settings()
    try:
        await asyncio.to_thread(
            _blocking_send, s.smtp_host, s.smtp_port, s.smtp_user, s.smtp_password,
            s.email_from_address, recipient, subject, text_body, html_body,
        )
    except Exception as exc:  # noqa: BLE001 — recorded, never swallowed
        logger.warning("Email to %s failed: %s", recipient, exc)
        return SendResult("failed", f"{type(exc).__name__}: {exc}"[:500])

    return SendResult("sent")
