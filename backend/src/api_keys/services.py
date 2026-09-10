"""API Key service functions."""

import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database.models import ApiKeyDB
from src.shared.settings import settings

# Get configured timezone
tz = pytz.timezone(settings.TIMEZONE)


def get_current_time() -> datetime:
    """Get current time in configured timezone as naive datetime."""
    utc_now = datetime.now(UTC)
    local_time = utc_now.astimezone(tz)
    return local_time.replace(tzinfo=None)


def generate_api_key() -> str:
    """Generate a secure random API key.

    Returns:
        A secure random API key in format: hyb_<random_string>
    """
    # Generate 32 bytes = 64 hex characters
    random_part = secrets.token_hex(32)
    return f"hyb_{random_part}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key using bcrypt.

    Args:
        api_key: The plain API key to hash

    Returns:
        The hashed API key
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(api_key.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash.

    Args:
        plain_key: The plain API key to verify
        hashed_key: The hashed API key to compare against

    Returns:
        True if the key matches, False otherwise
    """
    return bcrypt.checkpw(plain_key.encode("utf-8"), hashed_key.encode("utf-8"))


async def create_api_key(
    db: AsyncSession,
    user_id: int,
    name: str,
    expires_in_days: int | None = None,
) -> tuple[ApiKeyDB, str]:
    """Create a new API key for a user.

    Args:
        db: Database session
        user_id: ID of the user creating the key
        name: User-friendly name for the key
        expires_in_days: Optional number of days until expiration

    Returns:
        Tuple of (ApiKeyDB instance, plain API key)
    """
    # Generate the API key
    api_key = generate_api_key()

    # Extract prefix (first 8 characters after 'hyb_')
    prefix = api_key[:12]  # 'hyb_' + first 8 chars

    # Hash the key for storage
    key_hash = hash_api_key(api_key)

    # Calculate expiration date if specified
    expires_at = None
    if expires_in_days:
        expires_at = get_current_time() + timedelta(days=expires_in_days)

    # Create database record
    db_key = ApiKeyDB(
        user_id=user_id,
        key_hash=key_hash,
        name=name,
        prefix=prefix,
        expires_at=expires_at,
    )

    db.add(db_key)
    await db.commit()
    await db.refresh(db_key)

    return db_key, api_key


async def list_user_api_keys(db: AsyncSession, user_id: int) -> list[ApiKeyDB]:
    """List all API keys for a user.

    Args:
        db: Database session
        user_id: ID of the user

    Returns:
        List of ApiKeyDB instances
    """
    result = await db.execute(select(ApiKeyDB).where(ApiKeyDB.user_id == user_id).order_by(ApiKeyDB.created_at.desc()))
    return list(result.scalars().all())


async def revoke_api_key(db: AsyncSession, key_id: int, user_id: int) -> bool:
    """Revoke (delete) an API key.

    Args:
        db: Database session
        key_id: ID of the API key to revoke
        user_id: ID of the user (for authorization check)

    Returns:
        True if key was deleted, False if not found or unauthorized
    """
    result = await db.execute(select(ApiKeyDB).where(ApiKeyDB.id == key_id, ApiKeyDB.user_id == user_id))
    api_key = result.scalar_one_or_none()

    if not api_key:
        return False

    await db.delete(api_key)
    await db.commit()
    return True


async def verify_and_get_user_from_api_key(db: AsyncSession, api_key: str) -> ApiKeyDB | None:
    """Verify an API key and return the associated API key record.

    Args:
        db: Database session
        api_key: The plain API key to verify

    Returns:
        ApiKeyDB instance if valid and active, None otherwise
    """
    # Extract prefix for quick lookup
    prefix = api_key[:12]

    # Find all keys with matching prefix
    result = await db.execute(select(ApiKeyDB).where(ApiKeyDB.prefix == prefix, ApiKeyDB.is_active))
    potential_keys = result.scalars().all()

    # Verify the full key against each potential match
    for db_key in potential_keys:
        if verify_api_key(api_key, db_key.key_hash):
            # Check if key is expired
            if db_key.expires_at and get_current_time() > db_key.expires_at:
                return None

            # Update last_used_at
            db_key.last_used_at = get_current_time()
            await db.commit()

            return db_key

    return None
