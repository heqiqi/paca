"""Project management endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User
from app.schemas.project import (
    AddMemberRequest,
    CreateProjectRequest,
    CreateProjectRoleRequest,
    ProjectMemberResponse,
    ProjectResponse,
    ProjectRoleResponse,
    UpdateMemberRoleRequest,
    UpdateProjectRequest,
    UpdateProjectRoleRequest,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all projects the user has access to."""
    result = await db.execute(select(Project).where(Project.deleted_at.is_(None)).order_by(Project.created_at))
    projects = result.scalars().all()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: CreateProjectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a new project."""
    project = Project(
        name=body.name,
        description=body.description,
        task_id_prefix=body.task_id_prefix,
        is_public=body.is_public,
        created_by=current_user.user_id,
    )
    db.add(project)
    await db.flush()
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    body: UpdateProjectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    if body.task_id_prefix is not None:
        project.task_id_prefix = body.task_id_prefix
    if body.is_public is not None:
        project.is_public = body.is_public
    if body.settings is not None:
        project.settings = body.settings
    await db.flush()
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Soft-delete a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    project.deleted_at = datetime.now(UTC)
    await db.flush()


# --- Members ---


@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_members(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List project members."""
    result = await db.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id, ProjectMember.deleted_at.is_(None))
        .order_by(ProjectMember.created_at)
    )
    members = result.scalars().all()
    return [
        ProjectMemberResponse(
            id=m.id,
            project_id=m.project_id,
            user_id=m.user_id,
            username=m.user.username if m.user else "",
            full_name=m.user.full_name if m.user else "",
            role_name=m.role.role_name if m.role else "",
            project_role_id=m.project_role_id,
            created_at=m.created_at,
        )
        for m in members
    ]


@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: UUID,
    body: AddMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Add a member to the project."""
    member = ProjectMember(
        project_id=project_id,
        user_id=body.user_id,
        project_role_id=body.project_role_id,
    )
    db.add(member)
    await db.flush()
    return {"id": member.id, "message": "member added"}


@router.patch("/{project_id}/members/{member_id}")
async def update_member_role(
    project_id: UUID,
    member_id: UUID,
    body: UpdateMemberRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a member's role."""
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.id == member_id,
            ProjectMember.project_id == project_id,
            ProjectMember.deleted_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    member.project_role_id = body.project_role_id
    await db.flush()
    return {"message": "member role updated"}


@router.delete("/{project_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: UUID,
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove a member from the project (soft delete)."""
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.id == member_id,
            ProjectMember.project_id == project_id,
            ProjectMember.deleted_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    member.deleted_at = datetime.now(UTC)
    await db.flush()


# --- Roles ---


@router.get("/{project_id}/roles", response_model=list[ProjectRoleResponse])
async def list_roles(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List project roles."""
    result = await db.execute(
        select(ProjectRole).where(ProjectRole.project_id == project_id).order_by(ProjectRole.role_name)
    )
    roles = result.scalars().all()
    return [ProjectRoleResponse.model_validate(r) for r in roles]


@router.post("/{project_id}/roles", response_model=ProjectRoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    project_id: UUID,
    body: CreateProjectRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a project role."""
    role = ProjectRole(
        project_id=project_id,
        role_name=body.role_name,
        permissions=body.permissions,
    )
    db.add(role)
    await db.flush()
    return ProjectRoleResponse.model_validate(role)


@router.patch("/{project_id}/roles/{role_id}", response_model=ProjectRoleResponse)
async def update_role(
    project_id: UUID,
    role_id: UUID,
    body: UpdateProjectRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a project role."""
    result = await db.execute(
        select(ProjectRole).where(ProjectRole.id == role_id, ProjectRole.project_id == project_id)
    )
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    if body.role_name is not None:
        role.role_name = body.role_name
    if body.permissions is not None:
        role.permissions = body.permissions
    role.updated_at = datetime.now(UTC)
    await db.flush()
    return ProjectRoleResponse.model_validate(role)


@router.delete("/{project_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    project_id: UUID,
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a project role."""
    result = await db.execute(
        select(ProjectRole).where(ProjectRole.id == role_id, ProjectRole.project_id == project_id)
    )
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    await db.delete(role)
    await db.flush()
