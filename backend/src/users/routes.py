"""User management routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.audit import get_client_ip, log_action
from src.shared.auth.auth_simple import get_current_admin_user, get_current_user
from src.shared.database.database import get_db, hash_password
from src.shared.database.models import UserDB, UserNamespaceDB

from .models import UserCreate, UserListResponse, UserResponse, UserUpdate

users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        role=current_user["role"],
        is_active=current_user["is_active"],
        allowed_namespaces=current_user["allowed_namespaces"],
        created_at=current_user.get("created_at"),
        updated_at=current_user.get("updated_at"),
    )


@users_router.get("", response_model=UserListResponse)
async def list_users(
    admin_user: dict = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    """List all users (admin only)"""
    # Get total count
    result = await db.execute(select(UserDB))
    all_users = result.scalars().all()
    total = len(all_users)

    # Get paginated users
    result = await db.execute(select(UserDB).offset(skip).limit(limit))
    users = result.scalars().all()

    # Build response with allowed_namespaces
    user_responses = []
    for user in users:
        result = await db.execute(select(UserNamespaceDB).where(UserNamespaceDB.user_id == user.id))
        user_namespaces = result.scalars().all()
        allowed_namespaces = [un.namespace for un in user_namespaces]

        user_responses.append(
            UserResponse(
                id=user.id,
                email=user.email,
                role=user.role,
                is_active=user.is_active,
                allowed_namespaces=allowed_namespaces,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )

    return UserListResponse(users=user_responses, total=total)


@users_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    admin_user: dict = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user by ID (admin only)"""
    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get user's allowed namespaces
    result = await db.execute(select(UserNamespaceDB).where(UserNamespaceDB.user_id == user.id))
    user_namespaces = result.scalars().all()
    allowed_namespaces = [un.namespace for un in user_namespaces]

    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        allowed_namespaces=allowed_namespaces,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@users_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    request: Request,
    admin_user: dict = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (admin only)"""
    # Check if user with this email already exists
    result = await db.execute(select(UserDB).where(UserDB.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User with this email already exists")

    # Validate role
    if user_data.role not in ["admin", "user"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be 'admin' or 'user'")

    # Create user
    new_user = UserDB(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()  # Get the user ID

    # Add namespace permissions for non-admin users
    allowed_namespaces = []
    if user_data.role != "admin" and user_data.allowed_namespaces:
        for namespace in user_data.allowed_namespaces:
            user_namespace = UserNamespaceDB(user_id=new_user.id, namespace=namespace)
            db.add(user_namespace)
        allowed_namespaces = user_data.allowed_namespaces

    await db.commit()
    await db.refresh(new_user)

    # Log the action
    await log_action(
        user_email=admin_user["email"],
        action="create_user",
        resource_type="user",
        resource_id=str(new_user.id),
        details={"email": new_user.email, "role": new_user.role, "allowed_namespaces": allowed_namespaces},
        ip_address=get_client_ip(request),
    )

    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        is_active=new_user.is_active,
        allowed_namespaces=allowed_namespaces,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
    )


@users_router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    request: Request,
    admin_user: dict = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user (admin only)"""
    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Update fields
    if user_data.email is not None:
        # Check if email is already used by another user
        result = await db.execute(select(UserDB).where(UserDB.email == user_data.email, UserDB.id != user_id))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")
        user.email = user_data.email

    if user_data.password is not None:
        user.hashed_password = hash_password(user_data.password)

    if user_data.role is not None:
        if user_data.role not in ["admin", "user"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be 'admin' or 'user'")
        user.role = user_data.role

    if user_data.is_active is not None:
        user.is_active = user_data.is_active

    # Update namespace permissions
    if user_data.allowed_namespaces is not None:
        # Remove existing namespace permissions
        result = await db.execute(select(UserNamespaceDB).where(UserNamespaceDB.user_id == user_id))
        existing_namespaces = result.scalars().all()
        for ns in existing_namespaces:
            await db.delete(ns)

        # Flush to ensure deletions are applied before insertions
        await db.flush()

        # Add new namespace permissions (only for non-admin users)
        if user.role != "admin":
            for namespace in user_data.allowed_namespaces:
                user_namespace = UserNamespaceDB(user_id=user.id, namespace=namespace)
                db.add(user_namespace)

    await db.commit()
    await db.refresh(user)

    # Get updated allowed_namespaces
    result = await db.execute(select(UserNamespaceDB).where(UserNamespaceDB.user_id == user.id))
    user_namespaces = result.scalars().all()
    allowed_namespaces = [un.namespace for un in user_namespaces]

    # Log the action
    update_details = {"email": user.email, "role": user.role, "is_active": user.is_active}
    if user_data.password is not None:
        update_details["password_changed"] = True
    if user_data.allowed_namespaces is not None:
        update_details["allowed_namespaces"] = allowed_namespaces

    await log_action(
        user_email=admin_user["email"],
        action="update_user",
        resource_type="user",
        resource_id=str(user.id),
        details=update_details,
        ip_address=get_client_ip(request),
    )

    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        allowed_namespaces=allowed_namespaces,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    request: Request,
    admin_user: dict = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete user (admin only)"""
    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent deleting yourself
    if user.id == admin_user["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")

    # Save details for audit log before deleting
    user_details = {"email": user.email, "role": user.role}

    await db.delete(user)
    await db.commit()

    # Log the action
    await log_action(
        user_email=admin_user["email"],
        action="delete_user",
        resource_type="user",
        resource_id=str(user_id),
        details=user_details,
        ip_address=get_client_ip(request),
    )
