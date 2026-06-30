"""Admin endpoints: user management, global roles."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.security import hash_password
from app.models.global_role import GlobalRole
from app.models.user import User
from app.schemas.user import (
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# --- User management ---


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all users (admin only)."""
    result = await db.execute(select(User).where(User.deleted_at.is_(None)).order_by(User.created_at))
    users = result.scalars().all()
    return [
        UserResponse(
            id=u.id,
            username=u.username,
            full_name=u.full_name,
            role=u.role.name if u.role else "USER",
            must_change_password=u.must_change_password,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in users
    ]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a new user (admin only)."""
    # Check if username already exists
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    # Resolve role
    if body.role_id:
        role_result = await db.execute(select(GlobalRole).where(GlobalRole.id == body.role_id))
        role = role_result.scalar_one_or_none()
        if role is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role not found")
        role_id = body.role_id
    else:
        # Default to USER role
        role_result = await db.execute(select(GlobalRole).where(GlobalRole.name == "USER"))
        role = role_result.scalar_one_or_none()
        if role is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Default role not found")
        role_id = role.id

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role_id=role_id,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()

    return UserResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=role.name,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )



@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get user by ID (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role.name if user.role else "USER",
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/users/{user_id}", response_model=UserResponse)
async def admin_update_user(
    user_id: UUID,
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a user (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role_id is not None:
        user.role_id = body.role_id
    if body.must_change_password is not None:
        user.must_change_password = body.must_change_password
    user.updated_at = datetime.now(UTC)
    await db.flush()

    # Reload to get role name
    await db.refresh(user)
    return UserResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role.name if user.role else "USER",
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/users/{user_id}/password")
async def reset_password(
    user_id: UUID,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Reset a user's password (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = body.must_change_password
    user.updated_at = datetime.now(UTC)
    await db.flush()
    return {"message": "password reset"}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Soft-delete a user (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.deleted_at = datetime.now(UTC)
    await db.flush()


# --- Global role management ---


@router.get("/global-roles")
async def list_global_roles(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all global roles."""
    result = await db.execute(select(GlobalRole).order_by(GlobalRole.name))
    roles = result.scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "permissions": r.permissions,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in roles
    ]
