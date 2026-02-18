"""Stripe payment integration service."""

import logging
import uuid

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from config import FRONTEND_URL, STRIPE_SECRET_KEY
from services import database_service

# Configure Stripe
stripe.api_key = STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)


async def create_checkout_session(
    db: AsyncSession,
    email: str,
    package_id: uuid.UUID,
) -> str:
    """Create a Stripe Checkout session for purchasing a package.

    Args:
        db: Database session
        email: User's email address
        package_id: Package UUID to purchase

    Returns:
        Stripe Checkout Session URL

    Raises:
        ValueError: If package not found or invalid
    """
    # Get package details
    package = await database_service.get_package_by_id(db, package_id)
    if not package:
        raise ValueError(f"Package {package_id} not found")

    if not package.is_active:
        raise ValueError(f"Package {package_id} is not active")

    # Get or create user
    user = await database_service.get_or_create_user(db, email)

    # Determine checkout mode based on package type
    if package.package_type == "subscription":
        mode = "subscription"
        line_items = [
            {
                "price": package.stripe_price_id,
                "quantity": 1,
            }
        ]
    else:  # one_time
        mode = "payment"
        line_items = [
            {
                "price": package.stripe_price_id,
                "quantity": 1,
            }
        ]

    try:
        # Create Stripe Checkout Session
        session = stripe.checkout.Session.create(
            customer_email=email,
            line_items=line_items,
            mode=mode,
            success_url=f"{FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/cancelled",
            metadata={
                "user_id": str(user.id),
                "package_id": str(package_id),
                "email": email,
            },
        )

        # Create pending purchase record
        await database_service.create_purchase(
            db=db,
            user_id=user.id,
            package_id=package_id,
            stripe_session_id=session.id,
            amount_gbp=float(package.price_gbp),
            credits_purchased=package.credits,
            status="pending",
        )

        logger.info(
            f"Created Stripe checkout session {session.id} for user {email}, package {package.name}"
        )

        return session.url

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        raise ValueError(f"Failed to create checkout session: {str(e)}")


async def handle_checkout_completed(db: AsyncSession, session: dict) -> None:
    """Handle successful checkout completion.

    Args:
        db: Database session
        session: Stripe Checkout Session object
    """
    session_id = session["id"]
    metadata = session.get("metadata", {})
    user_id = uuid.UUID(metadata["user_id"])
    package_id = uuid.UUID(metadata["package_id"])

    logger.info(f"Processing completed checkout {session_id} for user {user_id}")

    # Update purchase status
    purchase = await database_service.update_purchase_status(
        db, session_id, "completed"
    )

    if not purchase:
        logger.error(f"Purchase not found for session {session_id}")
        return

    # Get package to determine type
    package = await database_service.get_package_by_id(db, package_id)
    if not package:
        logger.error(f"Package {package_id} not found")
        return

    if package.package_type == "one_time":
        # Add credits for one-time purchase
        if package.credits:
            await database_service.add_credits(db, user_id, package.credits)
            logger.info(f"Added {package.credits} credits to user {user_id}")
    elif package.package_type == "subscription":
        # Subscription activation handled by subscription.created webhook
        logger.info(f"Subscription checkout completed for user {user_id}, waiting for subscription.created event")


async def handle_subscription_created(db: AsyncSession, subscription: dict) -> None:
    """Handle subscription creation (activate unlimited access).

    Args:
        db: Database session
        subscription: Stripe Subscription object
    """
    customer_email = subscription.get("customer_email")
    subscription_id = subscription["id"]

    if not customer_email:
        logger.error(f"No customer email in subscription {subscription_id}")
        return

    logger.info(f"Activating subscription {subscription_id} for {customer_email}")

    # Get user
    user = await database_service.get_user_by_email(db, customer_email)
    if not user:
        logger.error(f"User not found for email {customer_email}")
        return

    # Activate unlimited subscription (expires when Stripe subscription ends)
    await database_service.activate_subscription(db, user.id, expires_at=None)

    logger.info(f"Activated unlimited subscription for user {user.id}")


async def handle_subscription_deleted(db: AsyncSession, subscription: dict) -> None:
    """Handle subscription cancellation (deactivate unlimited access).

    Args:
        db: Database session
        subscription: Stripe Subscription object
    """
    customer_email = subscription.get("customer_email")
    subscription_id = subscription["id"]

    if not customer_email:
        logger.error(f"No customer email in subscription {subscription_id}")
        return

    logger.info(f"Deactivating subscription {subscription_id} for {customer_email}")

    # Get user
    user = await database_service.get_user_by_email(db, customer_email)
    if not user:
        logger.error(f"User not found for email {customer_email}")
        return

    # Deactivate subscription
    await database_service.deactivate_subscription(db, user.id)

    logger.info(f"Deactivated subscription for user {user.id}")


def create_stripe_product_and_price(
    package_name: str,
    package_description: str,
    price_gbp: float,
    package_type: str,
) -> str:
    """Create a Stripe Product and Price.

    Args:
        package_name: Product name
        package_description: Product description
        price_gbp: Price in GBP
        package_type: 'one_time' or 'subscription'

    Returns:
        Stripe Price ID

    Raises:
        ValueError: If Stripe API call fails
    """
    try:
        # Create product
        product = stripe.Product.create(
            name=package_name,
            description=package_description,
        )

        # Create price
        price_params = {
            "product": product.id,
            "currency": "gbp",
            "unit_amount": int(price_gbp * 100),  # Convert to pence
        }

        if package_type == "subscription":
            price_params["recurring"] = {"interval": "month"}

        price = stripe.Price.create(**price_params)

        logger.info(
            f"Created Stripe product {product.id} and price {price.id} for {package_name}"
        )

        return price.id

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating product/price: {e}")
        raise ValueError(f"Failed to create Stripe product/price: {str(e)}")
