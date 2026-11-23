"""Authentication routes for user login."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database.database import get_db, hash_password, verify_password
from src.shared.database.models import UserDB

from .auth_simple import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    revoke_refresh_token,
    verify_and_get_user_from_refresh_token,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    """Login request model"""

    email: str
    password: str


class Token(BaseModel):
    """Token response model"""

    access_token: str
    refresh_token: str
    token_type: str
    email: str
    role: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request model"""

    refresh_token: str


@auth_router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login(request: Request, credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Login with email and password.

    Returns a JWT access token and a refresh token.

    Rate limit: 5 requests per minute per IP address.
    """
    logger.info(f"Login attempt for email: {credentials.email}")

    user = await authenticate_user(credentials.email, credentials.password, db)

    if not user:
        logger.warning(f"Failed login attempt for email: {credentials.email} from IP: {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token (30 minutes)
    access_token = create_access_token(data={"user_id": user.id, "email": user.email, "role": user.role})

    # Create refresh token (7 days)
    _, refresh_token = await create_refresh_token(db, user.id)

    logger.info(f"Successful login for email: {credentials.email}")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "email": user.email,
        "role": user.role,
    }


class ChangePasswordRequest(BaseModel):
    """Change password request model"""

    current_password: str
    new_password: str


@auth_router.post("/change-password")
@limiter.limit("3/minute")
async def change_password(
    http_request: Request,
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change the password for the current user.

    Requires the current password for verification.

    Rate limit: 3 requests per minute per IP address.
    """
    logger.info(f"Password change attempt for user: {current_user['email']}")

    # Get the user from the database
    result = await db.execute(select(UserDB).where(UserDB.id == current_user["id"]))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify current password
    if not verify_password(request.current_password, user.hashed_password):
        logger.warning(f"Failed password change attempt for user: {current_user['email']} - incorrect current password")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Update password
    user.hashed_password = hash_password(request.new_password)
    await db.commit()

    logger.info(f"Password changed successfully for user: {current_user['email']}")

    return {"message": "Password changed successfully"}


@auth_router.post("/refresh", response_model=Token)
@limiter.limit("10/minute")
async def refresh_access_token(request: Request, token_request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Refresh access token using a refresh token.

    Returns a new JWT access token and refresh token.

    Rate limit: 10 requests per minute per IP address.
    """
    logger.info("Refresh token request received")

    # Verify the refresh token
    user = await verify_and_get_user_from_refresh_token(db, token_request.refresh_token)

    if not user:
        logger.warning(f"Invalid or expired refresh token from IP: {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Revoke the old refresh token
    await revoke_refresh_token(db, token_request.refresh_token)

    # Create new access token (30 minutes)
    access_token = create_access_token(data={"user_id": user.id, "email": user.email, "role": user.role})

    # Create new refresh token (7 days)
    _, new_refresh_token = await create_refresh_token(db, user.id)

    logger.info(f"Tokens refreshed for user: {user.email}")
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "email": user.email,
        "role": user.role,
    }


@auth_router.post("/logout")
async def logout(token_request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Logout by revoking the refresh token.

    This prevents the refresh token from being used to get new access tokens.
    """
    logger.info("Logout request received")

    # Revoke the refresh token
    revoked = await revoke_refresh_token(db, token_request.refresh_token)

    if revoked:
        logger.info("Refresh token revoked successfully")
        return {"message": "Logged out successfully"}
    else:
        logger.warning("Refresh token not found or already revoked")
        return {"message": "Logged out successfully"}  # Return success even if token not found
