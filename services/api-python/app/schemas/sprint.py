"""Sprint and view request/response schemas."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SprintResponse(BaseModel):
    """Sprint response."""

    id: UUID
    project_id: UUID
    name: str
    start_date: date | None = None
    end_date: date | None = None
    goal: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateSprintRequest(BaseModel):
    """POST /sprints request body."""

    name: str = Field(..., min_length=1, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    goal: str | None = None


class UpdateSprintRequest(BaseModel):
    """PATCH /sprints/:id request body."""

    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    goal: str | None = None
    status: str | None = None


class ViewResponse(BaseModel):
    """Sprint view response."""

    id: UUID
    sprint_id: UUID | None = None
    project_id: UUID
    name: str
    view_type: str
    view_context: str
    config: dict[str, Any]
    position: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateViewRequest(BaseModel):
    """POST /views request body."""

    name: str = Field(..., min_length=1, max_length=200)
    sprint_id: UUID | None = None
    view_type: str = Field(default="table", pattern="^(table|board|roadmap|plugin)$")
    view_context: str = Field(default="sprint", pattern="^(sprint|backlog|timeline)$")
    config: dict[str, Any] = Field(default_factory=dict)


class UpdateViewRequest(BaseModel):
    """PATCH /views/:id request body."""

    name: str | None = None
    config: dict[str, Any] | None = None


class ReorderViewsRequest(BaseModel):
    """PUT /views/positions request body."""

    view_ids: list[UUID]


class ViewTaskPositionResponse(BaseModel):
    """View task position response."""

    id: UUID
    view_id: UUID
    task_id: UUID
    position: float
    group_key: str | None = None

    model_config = {"from_attributes": True}


class MoveTaskRequest(BaseModel):
    """PUT /views/:viewId/task-positions/:taskId request body."""

    position: float
    group_key: str | None = None


class BulkMoveTasksRequest(BaseModel):
    """PUT /views/:viewId/task-positions request body."""

    positions: list[MoveTaskRequest]
    task_ids: list[UUID]
