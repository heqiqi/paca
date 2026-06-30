"""View management endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.sprint import SprintView, ViewTaskPosition
from app.schemas.sprint import (
    CreateViewRequest,
    MoveTaskRequest,
    ReorderViewsRequest,
    UpdateViewRequest,
    ViewResponse,
    ViewTaskPositionResponse,
)

router = APIRouter(prefix="/projects/{project_id}/views", tags=["views"])


@router.get("/", response_model=list[ViewResponse])
async def list_views(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List views for a project."""
    result = await db.execute(
        select(SprintView).where(SprintView.project_id == project_id).order_by(SprintView.position)
    )
    return [ViewResponse.model_validate(v) for v in result.scalars().all()]


@router.post("/", response_model=ViewResponse, status_code=status.HTTP_201_CREATED)
async def create_view(
    project_id: UUID,
    body: CreateViewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a view."""
    view = SprintView(
        project_id=project_id,
        sprint_id=body.sprint_id,
        name=body.name,
        view_type=body.view_type,
        view_context=body.view_context,
        config=body.config,
    )
    db.add(view)
    await db.flush()
    return ViewResponse.model_validate(view)


@router.get("/{view_id}", response_model=ViewResponse)
async def get_view(
    project_id: UUID,
    view_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single view."""
    result = await db.execute(
        select(SprintView).where(SprintView.id == view_id, SprintView.project_id == project_id)
    )
    view = result.scalar_one_or_none()
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="View not found")
    return ViewResponse.model_validate(view)


@router.patch("/{view_id}", response_model=ViewResponse)
async def update_view(
    project_id: UUID,
    view_id: UUID,
    body: UpdateViewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a view."""
    result = await db.execute(
        select(SprintView).where(SprintView.id == view_id, SprintView.project_id == project_id)
    )
    view = result.scalar_one_or_none()
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="View not found")
    if body.name is not None:
        view.name = body.name
    if body.config is not None:
        view.config = body.config
    view.updated_at = datetime.now(UTC)
    await db.flush()
    return ViewResponse.model_validate(view)


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_view(
    project_id: UUID,
    view_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a view."""
    result = await db.execute(
        select(SprintView).where(SprintView.id == view_id, SprintView.project_id == project_id)
    )
    view = result.scalar_one_or_none()
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="View not found")
    await db.delete(view)
    await db.flush()


@router.put("/positions", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_views(
    project_id: UUID,
    body: ReorderViewsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Reorder views."""
    for idx, view_id in enumerate(body.view_ids):
        await db.execute(
            update(SprintView)
            .where(SprintView.id == view_id, SprintView.project_id == project_id)
            .values(position=float(idx), updated_at=datetime.now(UTC))
        )
    await db.flush()


@router.get("/{view_id}/task-positions", response_model=list[ViewTaskPositionResponse])
async def list_task_positions(
    project_id: UUID,
    view_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List task positions for a view."""
    result = await db.execute(
        select(ViewTaskPosition)
        .where(ViewTaskPosition.view_id == view_id)
        .order_by(ViewTaskPosition.position)
    )
    return [ViewTaskPositionResponse.model_validate(p) for p in result.scalars().all()]


@router.put("/{view_id}/task-positions/{task_id}")
async def move_task(
    project_id: UUID,
    view_id: UUID,
    task_id: UUID,
    body: MoveTaskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Move a task to a new position in the view."""
    result = await db.execute(
        select(ViewTaskPosition).where(
            ViewTaskPosition.view_id == view_id, ViewTaskPosition.task_id == task_id
        )
    )
    pos = result.scalar_one_or_none()
    if pos is None:
        pos = ViewTaskPosition(view_id=view_id, task_id=task_id, position=body.position, group_key=body.group_key)
        db.add(pos)
    else:
        pos.position = body.position
        pos.group_key = body.group_key
    await db.flush()
    return {"message": "task moved"}
