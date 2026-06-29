"""Document management endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.document import DocActivity, DocFolder, DocSnapshot, Document

router = APIRouter(prefix="/projects/{project_id}/docs", tags=["documents"])


# --- Folders ---


@router.get("/folders")
async def list_folders(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List document folders."""
    result = await db.execute(
        select(DocFolder).where(DocFolder.project_id == project_id).order_by(DocFolder.position)
    )
    folders = result.scalars().all()
    return [
        {"id": f.id, "project_id": f.project_id, "parent_id": f.parent_id,
         "name": f.name, "position": f.position, "created_at": f.created_at}
        for f in folders
    ]


@router.post("/folders", status_code=status.HTTP_201_CREATED)
async def create_folder(
    project_id: UUID,
    name: str,
    parent_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a document folder."""
    folder = DocFolder(project_id=project_id, parent_id=parent_id, name=name)
    db.add(folder)
    await db.flush()
    return {"id": folder.id, "name": folder.name}


# --- Documents ---


@router.get("/")
async def list_documents(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List documents for a project."""
    result = await db.execute(
        select(Document)
        .where(Document.project_id == project_id, Document.deleted_at.is_(None))
        .order_by(Document.position)
    )
    docs = result.scalars().all()
    return [
        {"id": d.id, "project_id": d.project_id, "folder_id": d.folder_id,
         "title": d.title, "position": d.position, "created_at": d.created_at, "updated_at": d.updated_at}
        for d in docs
    ]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_document(
    project_id: UUID,
    title: str = "Untitled",
    folder_id: UUID | None = None,
    content: dict | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a document."""
    doc = Document(project_id=project_id, folder_id=folder_id, title=title, content=content)
    db.add(doc)
    await db.flush()
    return {"id": doc.id, "title": doc.title}


@router.get("/{doc_id}")
async def get_document(
    project_id: UUID,
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single document."""
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id, Document.project_id == project_id, Document.deleted_at.is_(None)
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return {
        "id": doc.id, "project_id": doc.project_id, "folder_id": doc.folder_id,
        "title": doc.title, "content": doc.content, "position": doc.position,
        "created_at": doc.created_at, "updated_at": doc.updated_at,
    }


@router.patch("/{doc_id}")
async def update_document(
    project_id: UUID,
    doc_id: UUID,
    title: str | None = None,
    content: dict | None = None,
    folder_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a document."""
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id, Document.project_id == project_id, Document.deleted_at.is_(None)
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if title is not None:
        doc.title = title
    if content is not None:
        doc.content = content
    if folder_id is not None:
        doc.folder_id = folder_id
    doc.updated_at = datetime.now(UTC)
    await db.flush()
    return {"message": "document updated"}


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    project_id: UUID,
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Soft-delete a document."""
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id, Document.project_id == project_id, Document.deleted_at.is_(None)
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    doc.deleted_at = datetime.now(UTC)
    await db.flush()


# --- Snapshots ---


@router.get("/{doc_id}/snapshots")
async def list_snapshots(
    project_id: UUID,
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List document snapshots."""
    result = await db.execute(
        select(DocSnapshot)
        .where(DocSnapshot.document_id == doc_id)
        .order_by(DocSnapshot.snapshot_number.desc())
    )
    snapshots = result.scalars().all()
    return [
        {"id": s.id, "document_id": s.document_id, "title": s.title,
         "snapshot_number": s.snapshot_number, "created_at": s.created_at}
        for s in snapshots
    ]


@router.get("/{doc_id}/snapshots/{snapshot_id}")
async def get_snapshot(
    project_id: UUID,
    doc_id: UUID,
    snapshot_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a document snapshot."""
    result = await db.execute(
        select(DocSnapshot).where(DocSnapshot.id == snapshot_id, DocSnapshot.document_id == doc_id)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    return {
        "id": snapshot.id, "document_id": snapshot.document_id, "title": snapshot.title,
        "content": snapshot.content, "snapshot_number": snapshot.snapshot_number,
        "created_at": snapshot.created_at,
    }
