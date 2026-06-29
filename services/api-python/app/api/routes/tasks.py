"""Task management endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.task import (
    CustomFieldDefinition,
    Task,
    TaskActivity,
    TaskCounter,
    TaskLink,
    TaskStatus,
    TaskType,
)
from app.schemas.task import (
    AddCommentRequest,
    CreateCustomFieldDefinitionRequest,
    CreateTaskLinkRequest,
    CreateTaskRequest,
    CreateTaskStatusRequest,
    CreateTaskTypeRequest,
    CustomFieldDefinitionResponse,
    ReorderTaskStatusesRequest,
    TaskActivityResponse,
    TaskLinkResponse,
    TaskListResponse,
    TaskResponse,
    TaskStatusResponse,
    TaskTypeResponse,
    UpdateCommentRequest,
    UpdateCustomFieldDefinitionRequest,
    UpdateTaskRequest,
    UpdateTaskStatusRequest,
    UpdateTaskTypeRequest,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["tasks"])


# --- Task Types ---


@router.get("/task-types", response_model=list[TaskTypeResponse])
async def list_task_types(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List task types for a project."""
    result = await db.execute(
        select(TaskType).where(TaskType.project_id == project_id).order_by(TaskType.name)
    )
    return [TaskTypeResponse.model_validate(t) for t in result.scalars().all()]


@router.post("/task-types", response_model=TaskTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_task_type(
    project_id: UUID,
    body: CreateTaskTypeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a task type."""
    task_type = TaskType(
        project_id=project_id,
        name=body.name,
        icon=body.icon,
        color=body.color,
        description=body.description,
    )
    db.add(task_type)
    await db.flush()
    return TaskTypeResponse.model_validate(task_type)



@router.patch("/task-types/{type_id}", response_model=TaskTypeResponse)
async def update_task_type(
    project_id: UUID,
    type_id: UUID,
    body: UpdateTaskTypeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a task type."""
    result = await db.execute(
        select(TaskType).where(TaskType.id == type_id, TaskType.project_id == project_id)
    )
    tt = result.scalar_one_or_none()
    if tt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task type not found")
    if body.name is not None:
        tt.name = body.name
    if body.icon is not None:
        tt.icon = body.icon
    if body.color is not None:
        tt.color = body.color
    if body.description is not None:
        tt.description = body.description
    tt.updated_at = datetime.now(UTC)
    await db.flush()
    return TaskTypeResponse.model_validate(tt)


@router.delete("/task-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_type(
    project_id: UUID,
    type_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a task type."""
    result = await db.execute(
        select(TaskType).where(TaskType.id == type_id, TaskType.project_id == project_id)
    )
    tt = result.scalar_one_or_none()
    if tt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task type not found")
    await db.delete(tt)
    await db.flush()


# --- Task Statuses ---


@router.get("/task-statuses", response_model=list[TaskStatusResponse])
async def list_task_statuses(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List task statuses for a project."""
    result = await db.execute(
        select(TaskStatus).where(TaskStatus.project_id == project_id).order_by(TaskStatus.position)
    )
    return [TaskStatusResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/task-statuses", response_model=TaskStatusResponse, status_code=status.HTTP_201_CREATED)
async def create_task_status(
    project_id: UUID,
    body: CreateTaskStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a task status."""
    ts = TaskStatus(
        project_id=project_id,
        name=body.name,
        color=body.color,
        position=body.position,
        category=body.category,
    )
    db.add(ts)
    await db.flush()
    return TaskStatusResponse.model_validate(ts)


@router.patch("/task-statuses/{status_id}", response_model=TaskStatusResponse)
async def update_task_status(
    project_id: UUID,
    status_id: UUID,
    body: UpdateTaskStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a task status."""
    result = await db.execute(
        select(TaskStatus).where(TaskStatus.id == status_id, TaskStatus.project_id == project_id)
    )
    ts = result.scalar_one_or_none()
    if ts is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task status not found")
    if body.name is not None:
        ts.name = body.name
    if body.color is not None:
        ts.color = body.color
    if body.position is not None:
        ts.position = body.position
    if body.category is not None:
        ts.category = body.category
    ts.updated_at = datetime.now(UTC)
    await db.flush()
    return TaskStatusResponse.model_validate(ts)


@router.delete("/task-statuses/{status_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_status(
    project_id: UUID,
    status_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a task status."""
    result = await db.execute(
        select(TaskStatus).where(TaskStatus.id == status_id, TaskStatus.project_id == project_id)
    )
    ts = result.scalar_one_or_none()
    if ts is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task status not found")
    await db.delete(ts)
    await db.flush()


@router.put("/task-statuses/positions", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_task_statuses(
    project_id: UUID,
    body: ReorderTaskStatusesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Reorder task statuses."""
    for idx, status_id in enumerate(body.status_ids):
        await db.execute(
            update(TaskStatus)
            .where(TaskStatus.id == status_id, TaskStatus.project_id == project_id)
            .values(position=idx, updated_at=datetime.now(UTC))
        )
    await db.flush()



# --- Tasks ---


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    project_id: UUID,
    sprint_id: UUID | None = Query(default=None),
    status_id: UUID | None = Query(default=None),
    assignee_id: UUID | None = Query(default=None),
    task_type_id: UUID | None = Query(default=None),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List tasks with optional filtering."""
    query = select(Task).where(Task.project_id == project_id, Task.deleted_at.is_(None))
    if sprint_id:
        query = query.where(Task.sprint_id == sprint_id)
    if status_id:
        query = query.where(Task.status_id == status_id)
    if assignee_id:
        query = query.where(Task.assignee_id == assignee_id)
    if task_type_id:
        query = query.where(Task.task_type_id == task_type_id)

    query = query.order_by(Task.task_number.desc()).limit(page_size + 1)
    result = await db.execute(query)
    tasks = list(result.scalars().all())

    has_more = len(tasks) > page_size
    if has_more:
        tasks = tasks[:page_size]

    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in tasks],
        has_more=has_more,
    )


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: UUID,
    body: CreateTaskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a task."""
    # Increment task counter atomically
    counter_result = await db.execute(
        select(TaskCounter).where(TaskCounter.project_id == project_id).with_for_update()
    )
    counter = counter_result.scalar_one_or_none()
    if counter is None:
        counter = TaskCounter(project_id=project_id, last_value=0)
        db.add(counter)
        await db.flush()
        # Re-fetch with lock
        counter_result = await db.execute(
            select(TaskCounter).where(TaskCounter.project_id == project_id).with_for_update()
        )
        counter = counter_result.scalar_one()

    counter.last_value += 1
    task_number = counter.last_value

    task = Task(
        project_id=project_id,
        task_number=task_number,
        task_type_id=body.task_type_id,
        status_id=body.status_id,
        sprint_id=body.sprint_id,
        parent_task_id=body.parent_task_id,
        title=body.title,
        description=body.description,
        importance=body.importance,
        story_points=body.story_points,
        assignee_id=body.assignee_id,
        reporter_id=body.reporter_id,
        custom_fields=body.custom_fields,
        start_date=body.start_date,
        due_date=body.due_date,
        tags=body.tags,
    )
    db.add(task)
    await db.flush()
    return TaskResponse.model_validate(task)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    project_id: UUID,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single task."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.project_id == project_id, Task.deleted_at.is_(None))
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.get("/tasks/by-number/{task_number}", response_model=TaskResponse)
async def get_task_by_number(
    project_id: UUID,
    task_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a task by its project-scoped number."""
    result = await db.execute(
        select(Task).where(
            Task.project_id == project_id, Task.task_number == task_number, Task.deleted_at.is_(None)
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    project_id: UUID,
    task_id: UUID,
    body: UpdateTaskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a task."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.project_id == project_id, Task.deleted_at.is_(None))
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if body.title is not None:
        task.title = body.title
    if body.task_type_id is not None:
        task.task_type_id = body.task_type_id
    if body.status_id is not None:
        task.status_id = body.status_id
    if body.sprint_id is not None:
        task.sprint_id = body.sprint_id
    if body.parent_task_id is not None:
        task.parent_task_id = body.parent_task_id
    if body.description is not None:
        task.description = body.description
    if body.importance is not None:
        task.importance = body.importance
    if body.story_points is not None:
        task.story_points = body.story_points
    if body.assignee_id is not None:
        task.assignee_id = body.assignee_id
    if body.reporter_id is not None:
        task.reporter_id = body.reporter_id
    if body.custom_fields is not None:
        task.custom_fields = body.custom_fields
    if body.start_date is not None:
        task.start_date = body.start_date
    if body.due_date is not None:
        task.due_date = body.due_date
    if body.tags is not None:
        task.tags = body.tags
    task.updated_at = datetime.now(UTC)
    await db.flush()
    return TaskResponse.model_validate(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    project_id: UUID,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Soft-delete a task."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.project_id == project_id, Task.deleted_at.is_(None))
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    task.deleted_at = datetime.now(UTC)
    await db.flush()


# --- Task Links ---


@router.get("/tasks/{task_id}/links", response_model=list[TaskLinkResponse])
async def list_task_links(
    project_id: UUID,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List links for a task."""
    result = await db.execute(
        select(TaskLink).where(
            (TaskLink.source_task_id == task_id) | (TaskLink.target_task_id == task_id)
        )
    )
    links = result.scalars().all()
    responses = []
    for link in links:
        # Compute display_link_type from perspective of task_id
        if link.source_task_id == task_id:
            display_type = link.link_type
        else:
            display_map = {"blocks": "is_blocked_by", "duplicates": "is_duplicated_by", "relates_to": "relates_to"}
            display_type = display_map.get(link.link_type, link.link_type)
        responses.append(
            TaskLinkResponse(
                id=link.id,
                source_task_id=link.source_task_id,
                target_task_id=link.target_task_id,
                link_type=link.link_type,
                display_link_type=display_type,
                created_by=link.created_by,
                created_at=link.created_at,
            )
        )
    return responses


@router.post("/tasks/{task_id}/links", status_code=status.HTTP_201_CREATED)
async def create_task_link(
    project_id: UUID,
    task_id: UUID,
    body: CreateTaskLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a link between tasks."""
    link = TaskLink(
        source_task_id=task_id,
        target_task_id=body.target_task_id,
        link_type=body.link_type,
        created_by=current_user.user_id,
    )
    db.add(link)
    await db.flush()
    return {"id": link.id, "message": "link created"}


@router.delete("/tasks/{task_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_link(
    project_id: UUID,
    task_id: UUID,
    link_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a task link."""
    result = await db.execute(select(TaskLink).where(TaskLink.id == link_id))
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    await db.delete(link)
    await db.flush()


# --- Task Activities ---


@router.get("/tasks/{task_id}/activities", response_model=list[TaskActivityResponse])
async def list_task_activities(
    project_id: UUID,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List task activities."""
    result = await db.execute(
        select(TaskActivity)
        .where(TaskActivity.task_id == task_id, TaskActivity.deleted_at.is_(None))
        .order_by(TaskActivity.created_at)
    )
    activities = result.scalars().all()
    return [TaskActivityResponse.model_validate(a) for a in activities]


@router.post("/tasks/{task_id}/activities/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    project_id: UUID,
    task_id: UUID,
    body: AddCommentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Add a comment to a task."""
    activity = TaskActivity(
        task_id=task_id,
        actor_id=None,  # Would be resolved to member ID
        activity_type="comment",
        content=body.content,
    )
    db.add(activity)
    await db.flush()
    return {"id": activity.id, "message": "comment added"}


@router.patch("/tasks/{task_id}/activities/comments/{comment_id}")
async def update_comment(
    project_id: UUID,
    task_id: UUID,
    comment_id: UUID,
    body: UpdateCommentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a comment."""
    result = await db.execute(
        select(TaskActivity).where(
            TaskActivity.id == comment_id,
            TaskActivity.task_id == task_id,
            TaskActivity.activity_type == "comment",
            TaskActivity.deleted_at.is_(None),
        )
    )
    activity = result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    activity.content = body.content
    activity.updated_at = datetime.now(UTC)
    await db.flush()
    return {"message": "comment updated"}


@router.delete("/tasks/{task_id}/activities/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    project_id: UUID,
    task_id: UUID,
    comment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Soft-delete a comment."""
    result = await db.execute(
        select(TaskActivity).where(
            TaskActivity.id == comment_id,
            TaskActivity.task_id == task_id,
            TaskActivity.activity_type == "comment",
            TaskActivity.deleted_at.is_(None),
        )
    )
    activity = result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    activity.deleted_at = datetime.now(UTC)
    await db.flush()


# --- Custom Field Definitions ---


@router.get("/custom-fields", response_model=list[CustomFieldDefinitionResponse])
async def list_custom_field_definitions(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List custom field definitions for a project."""
    result = await db.execute(
        select(CustomFieldDefinition)
        .where(CustomFieldDefinition.project_id == project_id)
        .order_by(CustomFieldDefinition.display_name)
    )
    return [CustomFieldDefinitionResponse.model_validate(f) for f in result.scalars().all()]


@router.post("/custom-fields", response_model=CustomFieldDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_field_definition(
    project_id: UUID,
    body: CreateCustomFieldDefinitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a custom field definition."""
    field = CustomFieldDefinition(
        project_id=project_id,
        field_key=body.field_key,
        display_name=body.display_name,
        field_type=body.field_type,
        options=body.options,
        is_required=body.is_required,
    )
    db.add(field)
    await db.flush()
    return CustomFieldDefinitionResponse.model_validate(field)


@router.patch("/custom-fields/{field_id}", response_model=CustomFieldDefinitionResponse)
async def update_custom_field_definition(
    project_id: UUID,
    field_id: UUID,
    body: UpdateCustomFieldDefinitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a custom field definition."""
    result = await db.execute(
        select(CustomFieldDefinition).where(
            CustomFieldDefinition.id == field_id, CustomFieldDefinition.project_id == project_id
        )
    )
    field = result.scalar_one_or_none()
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom field not found")
    if body.display_name is not None:
        field.display_name = body.display_name
    if body.field_type is not None:
        field.field_type = body.field_type
    if body.options is not None:
        field.options = body.options
    if body.is_required is not None:
        field.is_required = body.is_required
    field.updated_at = datetime.now(UTC)
    await db.flush()
    return CustomFieldDefinitionResponse.model_validate(field)


@router.delete("/custom-fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_field_definition(
    project_id: UUID,
    field_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a custom field definition."""
    result = await db.execute(
        select(CustomFieldDefinition).where(
            CustomFieldDefinition.id == field_id, CustomFieldDefinition.project_id == project_id
        )
    )
    field = result.scalar_one_or_none()
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom field not found")
    await db.delete(field)
    await db.flush()
