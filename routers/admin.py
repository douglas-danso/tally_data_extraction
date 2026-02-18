"""Admin API endpoints with JWT authentication."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db
from services import auth_service, database_service, stripe_service

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer()


# =============================================================================
# Authentication Models
# =============================================================================


class LoginRequest(BaseModel):
    """Admin login credentials."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


# =============================================================================
# User Management Models
# =============================================================================


class UserResponse(BaseModel):
    """User information for admin view."""

    id: str
    email: str
    credits: int
    is_unlimited: bool
    unlimited_expires_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class AddCreditsRequest(BaseModel):
    """Request to manually add credits."""

    credits: int


class PurchaseResponse(BaseModel):
    """Purchase history item."""

    id: str
    package_name: str
    credits_purchased: int | None
    amount_gbp: float
    status: str
    purchased_at: datetime


# =============================================================================
# Package Management Models
# =============================================================================


class PackageResponse(BaseModel):
    """Package information for admin view."""

    id: str
    name: str
    description: str
    package_type: str
    credits: int | None
    price_gbp: float
    stripe_price_id: str
    is_active: bool
    display_order: int
    created_at: datetime

    class Config:
        from_attributes = True


class PackageCreateRequest(BaseModel):
    """Request to create a new package."""

    name: str
    description: str
    package_type: str  # 'one_time' or 'subscription'
    credits: int | None  # None for unlimited
    price_gbp: float
    display_order: int = 0
    create_stripe_product: bool = True  # Whether to create Stripe product/price


class PackageUpdateRequest(BaseModel):
    """Request to update a package."""

    name: str | None = None
    description: str | None = None
    price_gbp: float | None = None
    is_active: bool | None = None
    display_order: int | None = None


# =============================================================================
# Authentication Dependency
# =============================================================================


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> str:
    """Verify JWT token and return admin email.

    Args:
        credentials: HTTP Bearer token
        db: Database session

    Returns:
        Admin email

    Raises:
        HTTPException: If token is invalid or admin not found
    """
    token = credentials.credentials

    # Verify token
    email = auth_service.verify_token(token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if admin exists
    admin = await database_service.get_admin_by_email(db, email)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin user not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return email


# =============================================================================
# Authentication Endpoints
# =============================================================================


@router.post("/login", response_model=LoginResponse)
async def admin_login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Admin login endpoint.

    Args:
        request: Email and password

    Returns:
        JWT access token
    """
    # Get admin user
    admin = await database_service.get_admin_by_email(db, request.email)

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Verify password
    if not auth_service.verify_password(request.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Create JWT token
    access_token = auth_service.create_access_token(admin.email)

    return LoginResponse(access_token=access_token)


# =============================================================================
# User Management Endpoints
# =============================================================================


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    offset: int = 0,
    limit: int = 100,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all users with pagination.

    Requires admin authentication.
    """
    users = await database_service.get_all_users(db, offset=offset, limit=limit)

    return [
        UserResponse(
            id=str(user.id),
            email=user.email,
            credits=user.credits,
            is_unlimited=user.is_unlimited,
            unlimited_expires_at=user.unlimited_expires_at,
            created_at=user.created_at,
        )
        for user in users
    ]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get user details by ID.

    Requires admin authentication.
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = await database_service.get_user_by_id(db, user_uuid)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=str(user.id),
        email=user.email,
        credits=user.credits,
        is_unlimited=user.is_unlimited,
        unlimited_expires_at=user.unlimited_expires_at,
        created_at=user.created_at,
    )


@router.get("/users/{user_id}/purchases", response_model=list[PurchaseResponse])
async def get_user_purchases(
    user_id: str,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get purchase history for a user.

    Requires admin authentication.
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    purchases = await database_service.get_user_purchases(db, user_uuid)

    # Get package names for each purchase
    result = []
    for purchase in purchases:
        package = await database_service.get_package_by_id(db, purchase.package_id)
        result.append(
            PurchaseResponse(
                id=str(purchase.id),
                package_name=package.name if package else "Unknown",
                credits_purchased=purchase.credits_purchased,
                amount_gbp=float(purchase.amount_gbp),
                status=purchase.status,
                purchased_at=purchase.purchased_at,
            )
        )

    return result


@router.post("/users/{user_id}/credits")
async def add_user_credits(
    user_id: str,
    request: AddCreditsRequest,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Manually add credits to a user.

    Requires admin authentication.
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    if request.credits <= 0:
        raise HTTPException(status_code=400, detail="Credits must be positive")

    try:
        await database_service.add_credits(db, user_uuid, request.credits)
        return {"status": "success", "message": f"Added {request.credits} credits"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Package Management Endpoints
# =============================================================================


@router.get("/packages", response_model=list[PackageResponse])
async def list_all_packages(
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all packages (including inactive) for admin management.

    Requires admin authentication.
    """
    packages = await database_service.get_all_packages(db)

    return [
        PackageResponse(
            id=str(pkg.id),
            name=pkg.name,
            description=pkg.description,
            package_type=pkg.package_type,
            credits=pkg.credits,
            price_gbp=float(pkg.price_gbp),
            stripe_price_id=pkg.stripe_price_id,
            is_active=pkg.is_active,
            display_order=pkg.display_order,
            created_at=pkg.created_at,
        )
        for pkg in packages
    ]


@router.post("/packages", response_model=PackageResponse)
async def create_package(
    request: PackageCreateRequest,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new package.

    Optionally creates Stripe Product and Price.
    Requires admin authentication.
    """
    # Create Stripe product/price if requested
    if request.create_stripe_product:
        try:
            stripe_price_id = stripe_service.create_stripe_product_and_price(
                package_name=request.name,
                package_description=request.description,
                price_gbp=request.price_gbp,
                package_type=request.package_type,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(
            status_code=400,
            detail="Stripe Price ID must be created. Set create_stripe_product=True",
        )

    # Create package in database
    package = await database_service.create_package(
        db=db,
        name=request.name,
        description=request.description,
        package_type=request.package_type,
        price_gbp=request.price_gbp,
        stripe_price_id=stripe_price_id,
        credits=request.credits,
        display_order=request.display_order,
    )

    return PackageResponse(
        id=str(package.id),
        name=package.name,
        description=package.description,
        package_type=package.package_type,
        credits=package.credits,
        price_gbp=float(package.price_gbp),
        stripe_price_id=package.stripe_price_id,
        is_active=package.is_active,
        display_order=package.display_order,
        created_at=package.created_at,
    )


@router.put("/packages/{package_id}", response_model=PackageResponse)
async def update_package(
    package_id: str,
    request: PackageUpdateRequest,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a package.

    Requires admin authentication.
    """
    try:
        package_uuid = uuid.UUID(package_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid package ID format")

    # Build update dict from non-None fields
    update_data = {k: v for k, v in request.dict().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    package = await database_service.update_package(db, package_uuid, **update_data)

    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    return PackageResponse(
        id=str(package.id),
        name=package.name,
        description=package.description,
        package_type=package.package_type,
        credits=package.credits,
        price_gbp=float(package.price_gbp),
        stripe_price_id=package.stripe_price_id,
        is_active=package.is_active,
        display_order=package.display_order,
        created_at=package.created_at,
    )


@router.delete("/packages/{package_id}")
async def delete_package(
    package_id: str,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a package (set is_active=False).

    Requires admin authentication.
    """
    try:
        package_uuid = uuid.UUID(package_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid package ID format")

    success = await database_service.deactivate_package(db, package_uuid)

    if not success:
        raise HTTPException(status_code=404, detail="Package not found")

    return {"status": "success", "message": "Package deactivated"}
