"""Script to create an admin user and seed test packages."""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AdminUser, Package
from database.session import AsyncSessionLocal
from services.auth_service import hash_password


async def create_admin_user(email: str, password: str):
    """Create an admin user.

    Args:
        email: Admin email
        password: Plain text password (will be hashed)
    """
    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        from sqlalchemy import select

        result = await db.execute(select(AdminUser).where(AdminUser.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"❌ Admin user {email} already exists!")
            return

        # Create admin
        admin = AdminUser(
            id=uuid.uuid4(),
            email=email,
            password_hash=hash_password(password),
        )

        db.add(admin)
        await db.commit()

        print(f"✅ Admin user created:")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        print(f"   (Keep this safe!)")


async def seed_test_packages():
    """Seed database with test packages.

    Note: You'll need to create Stripe products manually or via admin API.
    """
    async with AsyncSessionLocal() as db:
        packages = [
            {
                "name": "Starter Pack",
                "description": "5 supporting statements",
                "package_type": "one_time",
                "credits": 5,
                "price_gbp": 19.99,
                "stripe_price_id": "price_test_starter",
                "display_order": 1,
            },
            {
                "name": "Professional Pack",
                "description": "15 supporting statements - Best Value!",
                "package_type": "one_time",
                "credits": 15,
                "price_gbp": 49.99,
                "stripe_price_id": "price_test_professional",
                "display_order": 2,
            },
            {
                "name": "Unlimited Monthly",
                "description": "Unlimited statements for one month",
                "package_type": "subscription",
                "credits": None,  # Unlimited
                "price_gbp": 29.99,
                "stripe_price_id": "price_test_unlimited",
                "display_order": 3,
            },
        ]

        for pkg_data in packages:
            package = Package(
                id=uuid.uuid4(),
                is_active=True,
                **pkg_data,
            )
            db.add(package)

        await db.commit()

        print("\n✅ Test packages created:")
        for pkg in packages:
            print(f"   - {pkg['name']}: £{pkg['price_gbp']}")
        print(
            "\n⚠️  Note: These use placeholder Stripe Price IDs."
        )
        print("   You'll need to create real Stripe products or use the admin API.")


async def main():
    """Main setup function."""
    print("=" * 60)
    print("NHS Supporting Information Generator - Initial Setup")
    print("=" * 60)

    # Create admin user
    print("\n📝 Creating admin user...")
    await create_admin_user(
        email="admin@example.com",
        password="admin123",  # Change this!
    )

    # Seed test packages
    print("\n📦 Creating test packages...")
    await seed_test_packages()

    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("\nNext steps:")
    print("1. Update Stripe Price IDs in packages via admin API")
    print("2. Login to admin dashboard with credentials above")
    print("3. Create real packages with proper Stripe integration")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
