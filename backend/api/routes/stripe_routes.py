"""
Stripe payment routes.
Security rules applied:
- Webhook signature ALWAYS verified before processing.
- Idempotency keys on all payment operations.
- Webhook-first: user tier updated via webhook, never from checkout response.
- Metadata threaded through every session so webhooks can identify users.
"""

import logging
import uuid
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.dependencies import DbDep, UserDep
from backend.config import get_settings
from backend.models.admin_log import AdminLog
from backend.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/stripe", tags=["stripe"])

_FALLBACK_PRICE_ID = "price_narrative_paid_699"   # $6.99/month — set STRIPE_PRICE_ID in env


def _get_price_id() -> str:
    return settings.stripe_price_id or _FALLBACK_PRICE_ID


def _stripe_client():
    stripe.api_key = settings.stripe_secret_key
    return stripe


@router.post("/checkout")
async def create_checkout_session(db: DbDep, user: UserDep) -> dict:
    """Create a Stripe Checkout session for upgrading to paid tier."""
    if user.tier == "paid":
        raise HTTPException(status_code=400, detail="Already on paid tier")

    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    s = _stripe_client()

    # Create/retrieve Stripe customer
    customer_id = user.stripe_customer_id
    if not customer_id:
        customer = s.Customer.create(
            email=user.email,
            metadata={"narrative_user_id": str(user.id)},
            idempotency_key=f"customer-{user.id}",
        )
        customer_id = customer.id
        user.stripe_customer_id = customer_id
        db.add(user)
        await db.flush()
        await db.commit()

    session = s.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": _get_price_id(), "quantity": 1}],
        mode="subscription",
        success_url="https://app.thenarrative.io/settings?upgraded=1",
        cancel_url="https://app.thenarrative.io/settings?cancelled=1",
        metadata={
            "narrative_user_id": str(user.id),
            "narrative_user_email": user.email,
        },
        subscription_data={
            "metadata": {
                "narrative_user_id": str(user.id),
            }
        },
        idempotency_key=f"checkout-{user.id}-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
    )

    return {"checkout_url": session.url, "session_id": session.id}


@router.post("/portal")
async def create_billing_portal(db: DbDep, user: UserDep) -> dict:
    """Create a Stripe Customer Portal session for managing subscription."""
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer found")

    s = _stripe_client()
    session = s.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url="https://app.thenarrative.io/settings",
    )
    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: DbDep) -> Response:
    """
    Stripe webhook endpoint.
    ALWAYS verify signature first — reject anything unverified.
    Handle webhooks as state transitions, not triggers.
    """
    if not settings.stripe_webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET not configured — rejecting webhook")
        raise HTTPException(status_code=503, detail="Webhook not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as exc:
        logger.error("Stripe webhook parse error: %s", exc)
        raise HTTPException(status_code=400, detail="Webhook parse error")

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info("Stripe webhook received: %s", event_type)

    # State machine — each event is a state transition
    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data, db)

    elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
        await _handle_subscription_updated(data, db)

    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data, db)

    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data, db)

    elif event_type == "invoice.payment_succeeded":
        await _handle_payment_succeeded(data, db)

    # Always return 200 to acknowledge receipt
    return Response(content="ok", status_code=200)


async def _get_user_by_stripe_metadata(data: dict, db) -> User | None:
    user_id = (
        data.get("metadata", {}).get("narrative_user_id")
        or data.get("subscription_data", {}).get("metadata", {}).get("narrative_user_id")
    )
    if user_id:
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        return result.scalar_one_or_none()

    # Fall back to customer_id lookup
    customer_id = data.get("customer")
    if customer_id:
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        return result.scalar_one_or_none()

    return None


async def _handle_checkout_completed(data: dict, db) -> None:
    user = await _get_user_by_stripe_metadata(data, db)
    if not user:
        logger.warning("checkout.session.completed: user not found in metadata")
        return

    user.tier = "paid"
    db.add(user)
    _log_stripe_event(user.id, "checkout_completed", db)
    await db.commit()
    logger.info("User %s upgraded to paid via checkout", user.email)


async def _handle_subscription_updated(data: dict, db) -> None:
    customer_id = data.get("customer")
    status = data.get("status")

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    if status == "active":
        user.tier = "paid"
    elif status in ("canceled", "unpaid", "past_due"):
        user.tier = "free"

    db.add(user)
    _log_stripe_event(user.id, f"subscription_{status}", db)
    await db.commit()
    logger.info("User %s subscription updated: status=%s tier=%s", user.email, status, user.tier)


async def _handle_subscription_deleted(data: dict, db) -> None:
    customer_id = data.get("customer")
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    user.tier = "free"
    db.add(user)
    _log_stripe_event(user.id, "subscription_deleted", db)
    await db.commit()
    logger.info("User %s downgraded to free: subscription deleted", user.email)


async def _handle_payment_failed(data: dict, db) -> None:
    customer_id = data.get("customer")
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    # Stripe handles dunning; we just log it
    _log_stripe_event(user.id, "payment_failed", db)
    await db.commit()
    logger.warning("Payment failed for user %s", user.email)


async def _handle_payment_succeeded(data: dict, db) -> None:
    customer_id = data.get("customer")
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    if user.tier != "paid":
        user.tier = "paid"
        db.add(user)

    _log_stripe_event(user.id, "payment_succeeded", db)
    await db.commit()


def _log_stripe_event(user_id, action: str, db) -> None:
    log = AdminLog(
        id=uuid.uuid4(),
        admin_id=None,
        action=f"stripe:{action}",
        target_type="user",
        target_id=user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
