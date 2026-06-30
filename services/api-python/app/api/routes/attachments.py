"""Attachment endpoints (presigned upload/download)."""

import uuid as uuid_mod
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.storage import delete_object, generate_presigned_download_url, generate_presigned_upload_url
from app.models.attachment import File, TaskAttachment

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/attachments", tags=["attachments"])


@router.get("/")
async def list_task_attachments(
    project_id: UUID,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List attachments for a task."""
    result = await db.execute(
        select(TaskAttachment, File)
        .join(File, TaskAttachment.file_id == File.id)
        .where(TaskAttachment.task_id == task_id)
        .order_by(TaskAttachment.created_at)
    )
    rows = result.all()
    return [
        {
            "id": att.id,
            "task_id": att.task_id,
            "file_id": att.file_id,
            "file_name": file.file_name,
            "content_type": file.content_type,
            "file_size": file.file_size,
            "created_at": att.created_at,
        }
        for att, file in rows
    ]


@router.post("/initiate-upload")
async def initiate_upload(
    project_id: UUID,
    task_id: UUID,
    file_name: str,
    content_type: str = "application/octet-stream",
    file_size: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Initiate a file upload and return a presigned URL."""
    storage_key = f"attachments/{project_id}/{task_id}/{uuid_mod.uuid4()}/{file_name}"

    # Create file record
    file = File(
        storage_key=storage_key,
        bucket=settings.storage_bucket,
        file_name=file_name,
        content_type=content_type,
        file_size=file_size,
        upload_status="pending",
        uploaded_by=current_user.user_id,
    )
    db.add(file)
    await db.flush()

    # Generate presigned upload URL
    upload_url = await generate_presigned_upload_url(storage_key, content_type)

    return {"file_id": file.id, "upload_url": upload_url, "storage_key": storage_key}


@router.post("/complete-upload")
async def complete_upload(
    project_id: UUID,
    task_id: UUID,
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Complete a file upload and attach it to the task."""
    result = await db.execute(select(File).where(File.id == file_id))
    file = result.scalar_one_or_none()
    if file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    file.upload_status = "uploaded"
    file.updated_at = datetime.now(UTC)

    attachment = TaskAttachment(
        task_id=task_id,
        file_id=file_id,
        created_by=current_user.user_id,
    )
    db.add(attachment)
    await db.flush()
    return {"id": attachment.id, "message": "upload completed"}


@router.get("/{attachment_id}/download-url")
async def get_download_url(
    project_id: UUID,
    task_id: UUID,
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a presigned download URL for an attachment."""
    result = await db.execute(
        select(TaskAttachment, File)
        .join(File, TaskAttachment.file_id == File.id)
        .where(TaskAttachment.id == attachment_id, TaskAttachment.task_id == task_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    _, file = row
    url = await generate_presigned_download_url(file.storage_key)
    return {"download_url": url}


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_attachment(
    project_id: UUID,
    task_id: UUID,
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete an attachment."""
    result = await db.execute(
        select(TaskAttachment, File)
        .join(File, TaskAttachment.file_id == File.id)
        .where(TaskAttachment.id == attachment_id, TaskAttachment.task_id == task_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    attachment, file = row
    await db.delete(attachment)
    await delete_object(file.storage_key)
    await db.delete(file)
    await db.flush()
