"""Authentication using database and JWT tokens."""

import datetime
import secrets

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database.database import get_db, verify_password
from src.shared.database.models import RefreshTokenDB, UserDB, UserNamespaceDB
from src.shared.settings import settings

security = HTTPBearer()


def create_access_token(data: dict, expires_delta: datetime.timedelta | None = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.UTC) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def authenticate_user(email: str, password: str, db: AsyncSession) -> UserDB | None:
    """Authenticate user with email and password"""
    result = await db.execute(select(UserDB).where(UserDB.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify JWT token or API key and return payload"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    # Check if it's an API key (starts with "hyb_")
    if token.startswith("hyb_"):
        # Verify API key
        from src.api_keys.services import verify_and_get_user_from_api_key

        api_key_record = await verify_and_get_user_from_api_key(db, token)
        if not api_key_record:
            raise credentials_exception

        # Get the user associated with this API key
        result = await db.execute(select(UserDB).where(UserDB.id == api_key_record.user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise credentials_exception

        return {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "auth_type": "api_key",
        }

    # Otherwise, treat it as a JWT token
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("user_id")
        email: str = payload.get("email")
        role: str = payload.get("role")

        if user_id is None or email is None or role is None:
            raise credentials_exception

        return {
            "user_id": user_id,
            "email": email,
            "role": role,
            "auth_type": "jwt",
        }
    except JWTError:
        raise credentials_exception


async def get_current_user(token_data: dict = Depends(verify_token), db: AsyncSession = Depends(get_db)) -> dict:
    """Get current authenticated user from database"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = token_data.get("user_id")
    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    # Get user's allowed namespaces (for non-admin users)
    allowed_namespaces = []
    if user.role != "admin":
        result = await db.execute(select(UserNamespaceDB).where(UserNamespaceDB.user_id == user.id))
        user_namespaces = result.scalars().all()
        allowed_namespaces = [un.namespace for un in user_namespaces]

    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "allowed_namespaces": allowed_namespaces,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


async def get_current_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency to verify current user is an admin"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user


def check_namespace_access(user: dict, namespace: str) -> bool:
    """Check if user has access to the specified namespace"""
    # Admins have access to all namespaces
    if user["role"] == "admin":
        return True

    # Regular users can only access their allowed namespaces
    return namespace in user["allowed_namespaces"]


def filter_namespaces_by_access(user: dict, namespaces: list[str]) -> list[str]:
    """Filter a list of namespaces to only include those the user has access to"""
    # Admins have access to all namespaces
    if user["role"] == "admin":
        return namespaces

    # Regular users can only see their allowed namespaces
    return [ns for ns in namespaces if ns in user["allowed_namespaces"]]


# Refresh Token Management


def generate_refresh_token() -> str:
    """Generate a secure random refresh token"""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(token.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_refresh_token(plain_token: str, hashed_token: str) -> bool:
    """Verify a refresh token against its hash"""
    return bcrypt.checkpw(plain_token.encode("utf-8"), hashed_token.encode("utf-8"))


async def create_refresh_token(db: AsyncSession, user_id: int) -> tuple[RefreshTokenDB, str]:
    """Create a new refresh token for a user

    Returns:
        Tuple of (RefreshTokenDB instance, plain refresh token)
    """
    from datetime import timedelta

    from src.shared.database.models import get_current_time

    # Generate the refresh token
    refresh_token = generate_refresh_token()

    # Hash the token for storage
    token_hash = hash_refresh_token(refresh_token)

    # Calculate expiration date (7 days from now)
    expires_at = get_current_time() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # Create database record
    db_token = RefreshTokenDB(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    db.add(db_token)
    await db.commit()
    await db.refresh(db_token)

    return db_token, refresh_token


async def verify_and_get_user_from_refresh_token(db: AsyncSession, refresh_token: str) -> UserDB | None:
    """Verify a refresh token and return the associated user

    Returns:
        UserDB instance if valid and active, None otherwise
    """
    from src.shared.database.models import get_current_time

    # Get all non-revoked refresh tokens
    result = await db.execute(select(RefreshTokenDB).where(not RefreshTokenDB.is_revoked))
    potential_tokens = result.scalars().all()

    # Verify the token against each potential match
    for db_token in potential_tokens:
        if verify_refresh_token(refresh_token, db_token.token_hash):
            # Check if token is expired
            if get_current_time() > db_token.expires_at:
                # Revoke expired token
                db_token.is_revoked = True
                await db.commit()
                return None

            # Get the user associated with this refresh token
            result = await db.execute(select(UserDB).where(UserDB.id == db_token.user_id))
            user = result.scalar_one_or_none()

            if user and user.is_active:
                return user

            return None

    return None


async def revoke_refresh_token(db: AsyncSession, refresh_token: str) -> bool:
    """Revoke a refresh token

    Returns:
        True if token was revoked, False if not found
    """
    # Get all non-revoked refresh tokens
    result = await db.execute(select(RefreshTokenDB).where(not RefreshTokenDB.is_revoked))
    potential_tokens = result.scalars().all()

    # Find and revoke the matching token
    for db_token in potential_tokens:
        if verify_refresh_token(refresh_token, db_token.token_hash):
            db_token.is_revoked = True
            await db.commit()
            return True

    return False
