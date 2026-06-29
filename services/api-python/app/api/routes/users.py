"""User management endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_user_from_db, require_jwt_auth
from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.api_key import APIKey
from app.models.global_role import GlobalRole
from app.models.user import User
from app.schemas.user import (
    ChangePasswordRequest,
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateMeRequest,
    UpdateUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_user_from_db)):
    """Get the current authenticated user."""
    return UserResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role.name if user.role else "USER",
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UpdateMeRequest,
    user: User = Depends(get_user_from_db),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile."""
    if body.full_name is not None:
        user.full_name = body.full_name
    user.updated_at = datetime.now(UTC)
    await db.flush()
    return UserResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role.name if user.role else "USER",
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/me/password")
async def change_my_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser = Depends(require_jwt_auth),
    db: AsyncSession = Depends(get_db),
):
    """Change the authenticated user's password."""
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.updated_at = datetime.now(UTC)
    await db.flush()
    return {"message": "password changed"}


@router.get("/me/global-permissions")
async def get_my_global_permissions(user: User = Depends(get_user_from_db)):
    """Get the current user's global permissions."""
    if user.role:
        return user.role.permissions
    return {}
