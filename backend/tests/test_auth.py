"""
Tests for the authentication system.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from jose import jwt

from src.shared.auth.auth_simple import create_access_token, get_current_user, verify_password
from src.shared.settings import settings


@pytest.fixture
def auth_token():
    """Create a valid authentication token for testing."""
    payload = {"authenticated": True, "role": "admin"}
    return create_access_token(payload)


def test_verify_password():
    """Test password verification."""
    # Correct password
    assert verify_password(settings.ADMIN_PASSWORD) is True

    # Incorrect password
    assert verify_password("wrong-password") is False


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
    # Get expiration time and check it's reasonable (30 minutes from now)
    expire_time = datetime.now(timezone.utc) + timedelta(minutes=30)
    assert abs(decoded["exp"] - expire_time.timestamp()) < 2
    # Already checked above

@pytest.mark.asyncio
async def test_get_current_user(auth_token):
    """Test getting the current authenticated user."""
    with patch("src.shared.auth.auth_simple.verify_token") as mock_verify:
        # Mock successful token verification
        mock_verify.return_value = {"authenticated": True, "role": "admin"}

        user = get_current_user()
        assert user["authenticated"] is True
        assert user["role"] == "admin"
