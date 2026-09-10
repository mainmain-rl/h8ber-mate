"""API Key management routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.audit import get_client_ip, log_action
from src.shared.auth.auth_simple import get_current_user
from src.shared.database.database import get_db

from .models import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse
from .services import create_api_key, list_user_api_keys, revoke_api_key

api_keys_router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@api_keys_router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the current user"""
    api_keys = await list_user_api_keys(db, current_user["id"])
    return [
        ApiKeyResponse(
            id=key.id,
            name=key.name,
            prefix=key.prefix,
            is_active=key.is_active,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            expires_at=key.expires_at,
        )
        for key in api_keys
    ]


@api_keys_router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_new_api_key(
    key_data: ApiKeyCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key for the current user

    The API key will be shown only once in the response.
    Make sure to save it securely as it cannot be retrieved later.
    """
    db_key, plain_key = await create_api_key(
        db=db,
        user_id=current_user["id"],
        name=key_data.name,
        expires_in_days=key_data.expires_in_days,
    )

    # Log the action
    await log_action(
        user_email=current_user["email"],
        action="create_api_key",
        resource_type="api_key",
        resource_id=str(db_key.id),
        details={"name": db_key.name, "expires_at": str(db_key.expires_at) if db_key.expires_at else None},
        ip_address=get_client_ip(request),
    )

    return ApiKeyCreatedResponse(
        id=db_key.id,
        name=db_key.name,
        prefix=db_key.prefix,
        api_key=plain_key,  # Only shown once
        is_active=db_key.is_active,
        created_at=db_key.created_at,
        expires_at=db_key.expires_at,
    )


@api_keys_router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke (delete) an API key"""
    success = await revoke_api_key(db, key_id, current_user["id"])

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    # Log the action
    await log_action(
        user_email=current_user["email"],
        action="delete_api_key",
        resource_type="api_key",
        resource_id=str(key_id),
        details={},
        ip_address=get_client_ip(request),
    )
