"""Database models."""

from datetime import UTC, datetime

import pytz
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from src.shared.settings import settings

from .database import Base

# Get configured timezone
tz = pytz.timezone(settings.TIMEZONE)


def get_current_time():
    """Get current time in configured timezone as naive datetime for PostgreSQL."""
    # Get current UTC time
    utc_now = datetime.now(UTC)
    # Convert to configured timezone
    local_time = utc_now.astimezone(tz)
    # Return as naive datetime (removing tzinfo) for PostgreSQL TIMESTAMP WITHOUT TIME ZONE
    return local_time.replace(tzinfo=None)


class ScheduleDB(Base):
    """SQLAlchemy model for schedules - simplified for single cluster"""

    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    namespace = Column(String, nullable=False, index=True)
    deployment_name = Column(String, nullable=False, index=True)
    scale_down_time = Column(String, nullable=False)  # Format: "HH:MM"
    scale_up_time = Column(String, nullable=False)  # Format: "HH:MM"
    original_replicas = Column(Integer, nullable=True)  # Null until first scale down
    enabled = Column(Boolean, default=True, nullable=False)
    is_scaled_down = Column(Boolean, default=False, nullable=False)
    last_scaled_at = Column(DateTime, nullable=True)  # Last time scaled up or down
    created_at = Column(DateTime, default=get_current_time, nullable=False)
    updated_at = Column(DateTime, default=get_current_time, onupdate=get_current_time, nullable=False)

    __table_args__ = (UniqueConstraint("namespace", "deployment_name", name="uix_namespace_deployment"),)


class UserDB(Base):
    """SQLAlchemy model for users with role-based access"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")  # 'admin' or 'user'
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=get_current_time, nullable=False)
    updated_at = Column(DateTime, default=get_current_time, onupdate=get_current_time, nullable=False)

    # Relationships
    namespaces = relationship("UserNamespaceDB", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("ApiKeyDB", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshTokenDB", back_populates="user", cascade="all, delete-orphan")


class UserNamespaceDB(Base):
    """SQLAlchemy model for user namespace permissions"""

    __tablename__ = "user_namespaces"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    namespace = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=get_current_time, nullable=False)

    # Relationships
    user = relationship("UserDB", back_populates="namespaces")

    __table_args__ = (UniqueConstraint("user_id", "namespace", name="uix_user_namespace"),)


class ApiKeyDB(Base):
    """SQLAlchemy model for API keys"""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String, unique=True, nullable=False, index=True)  # Hashed API key
    name = Column(String, nullable=False)  # User-friendly name for the key
    prefix = Column(String, nullable=False, index=True)  # First 8 chars for identification
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration
    created_at = Column(DateTime, default=get_current_time, nullable=False)

    # Relationships
    user = relationship("UserDB", back_populates="api_keys")


class RefreshTokenDB(Base):
    """SQLAlchemy model for refresh tokens"""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String, unique=True, nullable=False, index=True)  # Hashed refresh token
    expires_at = Column(DateTime, nullable=False)  # Refresh tokens expire after 7 days
    created_at = Column(DateTime, default=get_current_time, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)  # Can be revoked manually

    # Relationships
    user = relationship("UserDB", back_populates="refresh_tokens")
