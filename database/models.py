"""SQLAlchemy ORM models for the credit-based payment system."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class User(Base):
    """Email-based user accounts for credit tracking."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_unlimited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    unlimited_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    purchases: Mapped[list["Purchase"]] = relationship("Purchase", back_populates="user")
    credit_usage: Mapped[list["CreditUsage"]] = relationship("CreditUsage", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, credits={self.credits})>"


class Package(Base):
    """Configurable credit packages (one-time or subscription)."""

    __tablename__ = "packages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    package_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'one_time' or 'subscription'
    credits: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # NULL means unlimited
    price_gbp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    stripe_price_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    purchases: Mapped[list["Purchase"]] = relationship("Purchase", back_populates="package")

    def __repr__(self) -> str:
        return f"<Package(id={self.id}, name={self.name}, type={self.package_type})>"


class Purchase(Base):
    """Transaction history for credit purchases."""

    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id"), nullable=False
    )
    stripe_session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credits_purchased: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_gbp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'pending', 'completed', 'failed', 'refunded'
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="purchases")
    package: Mapped["Package"] = relationship("Package", back_populates="purchases")

    def __repr__(self) -> str:
        return f"<Purchase(id={self.id}, user_id={self.user_id}, status={self.status})>"


class CreditUsage(Base):
    """Audit log for credit consumption."""

    __tablename__ = "credit_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    credits_used: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    trust: Mapped[str] = mapped_column(String(255), nullable=False)
    submission_id: Mapped[str] = mapped_column(String(255), nullable=False)
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="credit_usage")

    def __repr__(self) -> str:
        return f"<CreditUsage(id={self.id}, user_id={self.user_id}, credits={self.credits_used})>"


class AdminUser(Base):
    """Admin authentication for dashboard access."""

    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<AdminUser(id={self.id}, email={self.email})>"
