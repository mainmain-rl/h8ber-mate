"""
Tests for the authentication system.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from jose import jwt

from src.shared.auth.auth_simple import create_access_token, get_current_user
from src.shared.database.database import hash_password, verify_password
from src.shared.settings import settings


def test_verify_password():
    """Test password verification."""
    hashed_password = hash_password(settings.ADMIN_PASSWORD)

    assert verify_password(settings.ADMIN_PASSWORD, hashed_password) is True
    assert verify_password("wrong-password", hashed_password) is False


@pytest.mark.asyncio
async def test_create_access_token():
    """Test creating access tokens."""
    # Test with default expiration
    token = create_access_token({"authenticated": True})
    decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert decoded["authenticated"] is True
    assert "exp" in decoded

    # Test with custom expiration time
    expire_delta = timedelta(minutes=30)  # 30 minutes
    token = create_access_token({"authenticated": True}, expires_delta=expire_delta)
    decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
    expire_time = datetime.now(UTC) + timedelta(minutes=30)
    assert abs(decoded["exp"] - expire_time.timestamp()) < 2

@pytest.mark.asyncio
async def test_get_current_user():
    """Test getting the current authenticated user."""
    user_record = SimpleNamespace(
        id=1,
        email="admin@example.com",
        role="admin",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db = Mock()
    db.execute = AsyncMock(return_value=Mock(scalar_one_or_none=Mock(return_value=user_record)))

    user = await get_current_user({"user_id": user_record.id}, db)

    assert user["id"] == user_record.id
    assert user["email"] == user_record.email
    assert user["role"] == "admin"
    assert user["allowed_namespaces"] == []
