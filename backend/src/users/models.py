"""Pydantic models for user management."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class UserBase(BaseModel):
    """Base user model"""

    email: str
    role: Literal["user", "admin"] = "user"


class UserCreate(UserBase):
    """User creation model"""

    password: str
    allowed_namespaces: list[str] = []  # Only used for non-admin users


class UserUpdate(BaseModel):
    """User update model"""

    email: str | None = None
    password: str | None = None
    role: str | None = None
    is_active: bool | None = None
    allowed_namespaces: list[str] | None = None


class UserResponse(UserBase):
    """User response model"""

    id: int
    is_active: bool
    allowed_namespaces: list[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """User list response model"""

    users: list[UserResponse]
    total: int
