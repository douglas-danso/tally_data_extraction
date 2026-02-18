"""Stripe webhook endpoint for payment events."""

import logging

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config import STRIPE_WEBHOOK_SECRET
from database.session import get_db
from services import stripe_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe-webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events.

    Supported events:
    - checkout.session.completed: Add credits after payment
    - customer.subscription.created: Activate unlimited subscription
    - customer.subscription.deleted: Deactivate unlimited subscription
    """
    if not stripe_signature:
        logger.error("Missing Stripe-Signature header")
        raise HTTPException(status_code=400, detail="Missing signature")

    # Get raw body for signature verification
    payload = await request.body()

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    logger.info(f"Received Stripe webhook: {event_type}")

    # Handle different event types
    try:
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            await stripe_service.handle_checkout_completed(db, session)

        elif event_type == "customer.subscription.created":
            subscription = event["data"]["object"]
            await stripe_service.handle_subscription_created(db, subscription)

        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            await stripe_service.handle_subscription_deleted(db, subscription)

        else:
            logger.info(f"Unhandled event type: {event_type}")

    except Exception as e:
        logger.error(f"Error processing webhook {event_type}: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

    return {"status": "success"}
