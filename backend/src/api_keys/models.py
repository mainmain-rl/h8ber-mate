"""API Key models for request/response validation."""

from datetime import datetime

from pydantic import BaseModel


class ApiKeyCreate(BaseModel):
    """Request model for creating an API key"""

    name: str
    expires_in_days: int | None = None  # Optional expiration in days


class ApiKeyResponse(BaseModel):
    """Response model for API key (without the actual key)"""

    id: int
    name: str
    prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None

    class Config:
        from_attributes = True


class ApiKeyCreatedResponse(BaseModel):
    """Response when a new API key is created (includes the actual key once)"""

    id: int
    name: str
    prefix: str
    api_key: str  # Full key shown only once at creation
    is_active: bool
    created_at: datetime
    expires_at: datetime | None

    class Config:
        from_attributes = True
