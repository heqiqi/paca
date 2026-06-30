"""Sprint management endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.sprint import Sprint
from app.schemas.sprint import CreateSprintRequest, SprintResponse, UpdateSprintRequest

router = APIRouter(prefix="/projects/{project_id}/sprints", tags=["sprints"])


@router.get("/", response_model=list[SprintResponse])
async def list_sprints(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List sprints for a project."""
    result = await db.execute(
        select(Sprint).where(Sprint.project_id == project_id).order_by(Sprint.created_at.desc())
    )
    return [SprintResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/", response_model=SprintResponse, status_code=status.HTTP_201_CREATED)
async def create_sprint(
    project_id: UUID,
    body: CreateSprintRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a sprint."""
    sprint = Sprint(
        project_id=project_id,
        name=body.name,
        start_date=body.start_date,
        end_date=body.end_date,
        goal=body.goal,
    )
    db.add(sprint)
    await db.flush()
    return SprintResponse.model_validate(sprint)


@router.get("/{sprint_id}", response_model=SprintResponse)
async def get_sprint(
    project_id: UUID,
    sprint_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single sprint."""
    result = await db.execute(
        select(Sprint).where(Sprint.id == sprint_id, Sprint.project_id == project_id)
    )
    sprint = result.scalar_one_or_none()
    if sprint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found")
    return SprintResponse.model_validate(sprint)


@router.patch("/{sprint_id}", response_model=SprintResponse)
async def update_sprint(
    project_id: UUID,
    sprint_id: UUID,
    body: UpdateSprintRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a sprint."""
    result = await db.execute(
        select(Sprint).where(Sprint.id == sprint_id, Sprint.project_id == project_id)
    )
    sprint = result.scalar_one_or_none()
    if sprint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found")

    if body.name is not None:
        sprint.name = body.name
    if body.start_date is not None:
        sprint.start_date = body.start_date
    if body.end_date is not None:
        sprint.end_date = body.end_date
    if body.goal is not None:
        sprint.goal = body.goal
    if body.status is not None:
        sprint.status = body.status
    sprint.updated_at = datetime.now(UTC)
    await db.flush()
    return SprintResponse.model_validate(sprint)


@router.delete("/{sprint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sprint(
    project_id: UUID,
    sprint_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a sprint."""
    result = await db.execute(
        select(Sprint).where(Sprint.id == sprint_id, Sprint.project_id == project_id)
    )
    sprint = result.scalar_one_or_none()
    if sprint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found")
    await db.delete(sprint)
    await db.flush()


@router.post("/{sprint_id}/complete", response_model=SprintResponse)
async def complete_sprint(
    project_id: UUID,
    sprint_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Mark a sprint as completed."""
    result = await db.execute(
        select(Sprint).where(Sprint.id == sprint_id, Sprint.project_id == project_id)
    )
    sprint = result.scalar_one_or_none()
    if sprint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found")
    sprint.status = "completed"
    sprint.updated_at = datetime.now(UTC)
    await db.flush()
    return SprintResponse.model_validate(sprint)
