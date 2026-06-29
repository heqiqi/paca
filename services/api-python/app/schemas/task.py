"""Task request/response schemas."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TaskTypeResponse(BaseModel):
    """Task type response."""

    id: UUID
    project_id: UUID
    name: str
    icon: str | None = None
    color: str | None = None
    description: str | None = None
    is_default: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateTaskTypeRequest(BaseModel):
    """POST /task-types request body."""

    name: str = Field(..., min_length=1, max_length=100)
    icon: str | None = None
    color: str | None = None
    description: str | None = None


class UpdateTaskTypeRequest(BaseModel):
    """PATCH /task-types/:id request body."""

    name: str | None = None
    icon: str | None = None
    color: str | None = None
    description: str | None = None


class TaskStatusResponse(BaseModel):
    """Task status response."""

    id: UUID
    project_id: UUID
    name: str
    color: str | None = None
    position: int
    category: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}



class CreateTaskStatusRequest(BaseModel):
    """POST /task-statuses request body."""

    name: str = Field(..., min_length=1, max_length=100)
    color: str | None = None
    position: int = 0
    category: str = Field(..., pattern="^(backlog|refinement|ready|todo|inprogress|done)$")


class UpdateTaskStatusRequest(BaseModel):
    """PATCH /task-statuses/:id request body."""

    name: str | None = None
    color: str | None = None
    position: int | None = None
    category: str | None = None


class ReorderTaskStatusesRequest(BaseModel):
    """PUT /task-statuses/positions request body."""

    status_ids: list[UUID]


class TaskResponse(BaseModel):
    """Task response."""

    id: UUID
    project_id: UUID
    task_number: int
    task_type_id: UUID | None = None
    status_id: UUID | None = None
    sprint_id: UUID | None = None
    parent_task_id: UUID | None = None
    title: str
    description: Any | None = None
    importance: int
    story_points: int | None = None
    assignee_id: UUID | None = None
    reporter_id: UUID | None = None
    custom_fields: dict[str, Any]
    start_date: date | None = None
    due_date: date | None = None
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateTaskRequest(BaseModel):
    """POST /tasks request body."""

    title: str = Field(..., min_length=1, max_length=500)
    task_type_id: UUID | None = None
    status_id: UUID | None = None
    sprint_id: UUID | None = None
    parent_task_id: UUID | None = None
    description: Any | None = None
    importance: int = 0
    story_points: int | None = None
    assignee_id: UUID | None = None
    reporter_id: UUID | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    start_date: date | None = None
    due_date: date | None = None
    tags: list[str] = Field(default_factory=list)


class UpdateTaskRequest(BaseModel):
    """PATCH /tasks/:id request body."""

    title: str | None = None
    task_type_id: UUID | None = None
    status_id: UUID | None = None
    sprint_id: UUID | None = None
    parent_task_id: UUID | None = None
    description: Any | None = None
    importance: int | None = None
    story_points: int | None = None
    assignee_id: UUID | None = None
    reporter_id: UUID | None = None
    custom_fields: dict[str, Any] | None = None
    start_date: date | None = None
    due_date: date | None = None
    tags: list[str] | None = None


class TaskListResponse(BaseModel):
    """Paginated task list response."""

    items: list[TaskResponse]
    has_more: bool


class TaskLinkResponse(BaseModel):
    """Task link response."""

    id: UUID
    source_task_id: UUID
    target_task_id: UUID
    link_type: str
    display_link_type: str
    created_by: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateTaskLinkRequest(BaseModel):
    """POST /tasks/:id/links request body."""

    target_task_id: UUID
    link_type: str = Field(..., pattern="^(blocks|relates_to|duplicates)$")


class TaskActivityResponse(BaseModel):
    """Task activity response."""

    id: UUID
    task_id: UUID
    actor_id: UUID | None = None
    actor_name: str | None = None
    actor_username: str | None = None
    activity_type: str
    content: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AddCommentRequest(BaseModel):
    """POST /tasks/:id/activities/comments request body."""

    content: dict[str, Any]


class UpdateCommentRequest(BaseModel):
    """PATCH /tasks/:id/activities/comments/:commentId request body."""

    content: dict[str, Any]


class CustomFieldDefinitionResponse(BaseModel):
    """Custom field definition response."""

    id: UUID
    project_id: UUID
    field_key: str
    display_name: str
    field_type: str
    options: list[str] | None = None
    is_required: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateCustomFieldDefinitionRequest(BaseModel):
    """POST /custom-fields request body."""

    field_key: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    field_type: str = Field(..., pattern="^(text|number|date|select|multi_select|boolean|url)$")
    options: list[str] | None = None
    is_required: bool = False


class UpdateCustomFieldDefinitionRequest(BaseModel):
    """PATCH /custom-fields/:id request body."""

    display_name: str | None = None
    field_type: str | None = None
    options: list[str] | None = None
    is_required: bool | None = None
