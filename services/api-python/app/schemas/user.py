"""User request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    """User response (public fields only, no password_hash)."""

    id: UUID
    username: str
    full_name: str
    role: str
    must_change_password: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateUserRequest(BaseModel):
    """POST /admin/users request body."""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8)
    full_name: str = Field(default="")
    role_id: UUID | None = None


class UpdateUserRequest(BaseModel):
    """PATCH /admin/users/:id request body."""

    full_name: str | None = None
    role_id: UUID | None = None
    must_change_password: bool | None = None


class UpdateMeRequest(BaseModel):
    """PATCH /users/me request body."""

    full_name: str | None = None


class ChangePasswordRequest(BaseModel):
    """PATCH /users/me/password request body."""

    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)


class ResetPasswordRequest(BaseModel):
    """PATCH /admin/users/:id/password request body."""

    new_password: str = Field(..., min_length=8)
    must_change_password: bool = Field(default=True)
