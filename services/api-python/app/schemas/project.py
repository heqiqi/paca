"""Project request/response schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectResponse(BaseModel):
    """Project response."""

    id: UUID
    name: str
    description: str
    task_id_prefix: str
    is_public: bool
    settings: dict[str, Any]
    created_by: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateProjectRequest(BaseModel):
    """POST /projects request body."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")
    task_id_prefix: str = Field(default="", max_length=10)
    is_public: bool = Field(default=False)


class UpdateProjectRequest(BaseModel):
    """PATCH /projects/:id request body."""

    name: str | None = None
    description: str | None = None
    task_id_prefix: str | None = None
    is_public: bool | None = None
    settings: dict[str, Any] | None = None


class ProjectMemberResponse(BaseModel):
    """Project member response."""

    id: UUID
    project_id: UUID
    user_id: UUID
    username: str
    full_name: str
    role_name: str
    project_role_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    """POST /projects/:id/members request body."""

    user_id: UUID
    project_role_id: UUID


class UpdateMemberRoleRequest(BaseModel):
    """PATCH /projects/:id/members/:memberId request body."""

    project_role_id: UUID


class ProjectRoleResponse(BaseModel):
    """Project role response."""

    id: UUID
    project_id: UUID | None
    role_name: str
    permissions: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateProjectRoleRequest(BaseModel):
    """POST /projects/:id/roles request body."""

    role_name: str = Field(..., min_length=1, max_length=100)
    permissions: dict[str, Any] = Field(default_factory=dict)


class UpdateProjectRoleRequest(BaseModel):
    """PATCH /projects/:id/roles/:roleId request body."""

    role_name: str | None = None
    permissions: dict[str, Any] | None = None
