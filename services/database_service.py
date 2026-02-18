"""Database service for credit management and user operations."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AdminUser, CreditUsage, Package, Purchase, User


# =============================================================================
# User Management
# =============================================================================


async def get_or_create_user(db: AsyncSession, email: str) -> User:
    """Get existing user or create a new one with 0 credits.

    Args:
        db: Database session
        email: User's email address

    Returns:
        User object
    """
    # Try to get existing user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        return user

    # Create new user with 0 credits
    new_user = User(
        id=uuid.uuid4(),
        email=email,
        credits=0,
        is_unlimited=False,
        unlimited_expires_at=None,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Get user by email address.

    Args:
        db: Database session
        email: User's email address

    Returns:
        User object or None if not found
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Get user by ID.

    Args:
        db: Database session
        user_id: User's UUID

    Returns:
        User object or None if not found
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_all_users(
    db: AsyncSession, offset: int = 0, limit: int = 100
) -> list[User]:
    """Get all users with pagination.

    Args:
        db: Database session
        offset: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of User objects
    """
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


# =============================================================================
# Credit Operations
# =============================================================================


async def check_user_credits(db: AsyncSession, email: str) -> tuple[bool, int]:
    """Check if user has credits available.

    Args:
        db: Database session
        email: User's email address

    Returns:
        Tuple of (has_credits: bool, available_credits: int)
    """
    user = await get_user_by_email(db, email)

    if not user:
        return False, 0

    # Check if user has active unlimited subscription
    if user.is_unlimited:
        if user.unlimited_expires_at is None or user.unlimited_expires_at > datetime.utcnow():
            return True, -1  # -1 indicates unlimited

    # Check regular credits
    return user.credits > 0, user.credits


async def deduct_credit(db: AsyncSession, user_id: uuid.UUID, credits: int = 1) -> None:
    """Deduct credits from user's balance.

    Args:
        db: Database session
        user_id: User's UUID
        credits: Number of credits to deduct (default: 1)

    Raises:
        ValueError: If user doesn't have enough credits
    """
    user = await get_user_by_id(db, user_id)

    if not user:
        raise ValueError(f"User {user_id} not found")

    # Don't deduct if unlimited subscription is active
    if user.is_unlimited:
        if user.unlimited_expires_at is None or user.unlimited_expires_at > datetime.utcnow():
            return

    if user.credits < credits:
        raise ValueError(f"User {user_id} has insufficient credits")

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(credits=User.credits - credits, updated_at=datetime.utcnow())
    )
    await db.commit()


async def add_credits(db: AsyncSession, user_id: uuid.UUID, credits: int) -> None:
    """Add credits to user's balance.

    Args:
        db: Database session
        user_id: User's UUID
        credits: Number of credits to add
    """
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(credits=User.credits + credits, updated_at=datetime.utcnow())
    )
    await db.commit()


async def log_credit_usage(
    db: AsyncSession,
    user_id: uuid.UUID,
    credits_used: int,
    role: str,
    trust: str,
    submission_id: str,
) -> CreditUsage:
    """Log credit usage for audit trail.

    Args:
        db: Database session
        user_id: User's UUID
        credits_used: Number of credits used
        role: Job role
        trust: NHS trust
        submission_id: Tally submission ID

    Returns:
        CreditUsage object
    """
    usage = CreditUsage(
        id=uuid.uuid4(),
        user_id=user_id,
        credits_used=credits_used,
        role=role,
        trust=trust,
        submission_id=submission_id,
    )
    db.add(usage)
    await db.commit()
    await db.refresh(usage)
    return usage


# =============================================================================
# Subscription Management
# =============================================================================


async def activate_subscription(
    db: AsyncSession, user_id: uuid.UUID, expires_at: datetime | None = None
) -> None:
    """Activate unlimited subscription for user.

    Args:
        db: Database session
        user_id: User's UUID
        expires_at: Expiration datetime (None for never expires)
    """
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            is_unlimited=True,
            unlimited_expires_at=expires_at,
            updated_at=datetime.utcnow(),
        )
    )
    await db.commit()


async def deactivate_subscription(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Deactivate unlimited subscription for user.

    Args:
        db: Database session
        user_id: User's UUID
    """
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            is_unlimited=False,
            unlimited_expires_at=None,
            updated_at=datetime.utcnow(),
        )
    )
    await db.commit()


# =============================================================================
# Package Management
# =============================================================================


async def get_active_packages(db: AsyncSession) -> list[Package]:
    """Get all active packages ordered by display_order.

    Args:
        db: Database session

    Returns:
        List of active Package objects
    """
    result = await db.execute(
        select(Package)
        .where(Package.is_active == True)  # noqa: E712
        .order_by(Package.display_order)
    )
    return list(result.scalars().all())


async def get_package_by_id(db: AsyncSession, package_id: uuid.UUID) -> Package | None:
    """Get package by ID.

    Args:
        db: Database session
        package_id: Package UUID

    Returns:
        Package object or None if not found
    """
    result = await db.execute(select(Package).where(Package.id == package_id))
    return result.scalar_one_or_none()


async def get_all_packages(db: AsyncSession) -> list[Package]:
    """Get all packages (including inactive) for admin view.

    Args:
        db: Database session

    Returns:
        List of all Package objects
    """
    result = await db.execute(select(Package).order_by(Package.display_order))
    return list(result.scalars().all())


async def create_package(
    db: AsyncSession,
    name: str,
    description: str,
    package_type: str,
    price_gbp: float,
    stripe_price_id: str,
    credits: int | None = None,
    display_order: int = 0,
) -> Package:
    """Create a new package.

    Args:
        db: Database session
        name: Package name
        description: Package description
        package_type: 'one_time' or 'subscription'
        price_gbp: Price in GBP
        stripe_price_id: Stripe Price ID
        credits: Number of credits (None for unlimited)
        display_order: Display order

    Returns:
        Created Package object
    """
    package = Package(
        id=uuid.uuid4(),
        name=name,
        description=description,
        package_type=package_type,
        credits=credits,
        price_gbp=price_gbp,
        stripe_price_id=stripe_price_id,
        is_active=True,
        display_order=display_order,
    )
    db.add(package)
    await db.commit()
    await db.refresh(package)
    return package


async def update_package(
    db: AsyncSession,
    package_id: uuid.UUID,
    **kwargs,
) -> Package | None:
    """Update package fields.

    Args:
        db: Database session
        package_id: Package UUID
        **kwargs: Fields to update

    Returns:
        Updated Package object or None if not found
    """
    package = await get_package_by_id(db, package_id)
    if not package:
        return None

    for key, value in kwargs.items():
        if hasattr(package, key):
            setattr(package, key, value)

    package.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(package)
    return package


async def deactivate_package(db: AsyncSession, package_id: uuid.UUID) -> bool:
    """Soft delete package by setting is_active=False.

    Args:
        db: Database session
        package_id: Package UUID

    Returns:
        True if package was deactivated, False if not found
    """
    result = await update_package(db, package_id, is_active=False)
    return result is not None


# =============================================================================
# Purchase Management
# =============================================================================


async def create_purchase(
    db: AsyncSession,
    user_id: uuid.UUID,
    package_id: uuid.UUID,
    stripe_session_id: str,
    amount_gbp: float,
    credits_purchased: int | None = None,
    stripe_subscription_id: str | None = None,
    status: str = "pending",
) -> Purchase:
    """Create a purchase record.

    Args:
        db: Database session
        user_id: User's UUID
        package_id: Package UUID
        stripe_session_id: Stripe Checkout Session ID
        amount_gbp: Amount paid in GBP
        credits_purchased: Number of credits purchased (None for unlimited)
        stripe_subscription_id: Stripe Subscription ID (for recurring)
        status: Purchase status (default: 'pending')

    Returns:
        Created Purchase object
    """
    purchase = Purchase(
        id=uuid.uuid4(),
        user_id=user_id,
        package_id=package_id,
        stripe_session_id=stripe_session_id,
        stripe_subscription_id=stripe_subscription_id,
        credits_purchased=credits_purchased,
        amount_gbp=amount_gbp,
        status=status,
    )
    db.add(purchase)
    await db.commit()
    await db.refresh(purchase)
    return purchase


async def update_purchase_status(
    db: AsyncSession, stripe_session_id: str, status: str
) -> Purchase | None:
    """Update purchase status by Stripe session ID.

    Args:
        db: Database session
        stripe_session_id: Stripe Checkout Session ID
        status: New status ('completed', 'failed', 'refunded')

    Returns:
        Updated Purchase object or None if not found
    """
    result = await db.execute(
        select(Purchase).where(Purchase.stripe_session_id == stripe_session_id)
    )
    purchase = result.scalar_one_or_none()

    if not purchase:
        return None

    purchase.status = status
    await db.commit()
    await db.refresh(purchase)
    return purchase


async def get_user_purchases(
    db: AsyncSession, user_id: uuid.UUID
) -> list[Purchase]:
    """Get all purchases for a user.

    Args:
        db: Database session
        user_id: User's UUID

    Returns:
        List of Purchase objects
    """
    result = await db.execute(
        select(Purchase)
        .where(Purchase.user_id == user_id)
        .order_by(Purchase.purchased_at.desc())
    )
    return list(result.scalars().all())


# =============================================================================
# Admin User Management
# =============================================================================


async def get_admin_by_email(db: AsyncSession, email: str) -> AdminUser | None:
    """Get admin user by email.

    Args:
        db: Database session
        email: Admin email

    Returns:
        AdminUser object or None if not found
    """
    result = await db.execute(select(AdminUser).where(AdminUser.email == email))
    return result.scalar_one_or_none()


async def create_admin_user(
    db: AsyncSession, email: str, password_hash: str
) -> AdminUser:
    """Create a new admin user.

    Args:
        db: Database session
        email: Admin email
        password_hash: Bcrypt hashed password

    Returns:
        Created AdminUser object
    """
    admin = AdminUser(
        id=uuid.uuid4(),
        email=email,
        password_hash=password_hash,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin
