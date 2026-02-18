"""Public API endpoints for package listing and checkout."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db
from services import database_service, stripe_service

router = APIRouter(prefix="/api", tags=["packages"])


class PackageResponse(BaseModel):
    """Package information for frontend display."""

    id: str
    name: str
    description: str
    package_type: str
    credits: int | None
    price_gbp: float
    display_order: int

    class Config:
        from_attributes = True


class CheckoutRequest(BaseModel):
    """Request to create a checkout session."""

    email: EmailStr
    package_id: str


class CheckoutResponse(BaseModel):
    """Response with Stripe checkout URL."""

    checkout_url: str


@router.get("/packages", response_model=list[PackageResponse])
async def list_packages(db: AsyncSession = Depends(get_db)):
    """Get all active packages for display on the frontend.

    Returns packages ordered by display_order.
    """
    packages = await database_service.get_active_packages(db)

    return [
        PackageResponse(
            id=str(pkg.id),
            name=pkg.name,
            description=pkg.description,
            package_type=pkg.package_type,
            credits=pkg.credits,
            price_gbp=float(pkg.price_gbp),
            display_order=pkg.display_order,
        )
        for pkg in packages
    ]


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest, db: AsyncSession = Depends(get_db)
):
    """Create a Stripe Checkout session for purchasing a package.

    Args:
        request: Email and package ID

    Returns:
        Stripe Checkout URL to redirect user to
    """
    try:
        package_id = uuid.UUID(request.package_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid package ID format")

    try:
        checkout_url = await stripe_service.create_checkout_session(
            db=db,
            email=request.email,
            package_id=package_id,
        )

        return CheckoutResponse(checkout_url=checkout_url)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")
