from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import List, Optional

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, RoleEnum
from app.models.attachment import Attachment
from app.services import s3_service

router = APIRouter(tags=["attachments"])


@router.post("/upload", status_code=201)
async def upload_attachment(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    entity_id: int = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file and attach it to an entity (entity_type: 'user', 'workout', 'progress')."""
    allowed_entity_types = {"user", "workout", "progress"}
    if entity_type not in allowed_entity_types:
        raise HTTPException(status_code=400, detail=f"entity_type must be one of: {allowed_entity_types}")

    s3_key, content_type, size = await s3_service.upload_file(file)

    attachment = Attachment(
        user_id=current_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        filename=file.filename or "file",
        s3_key=s3_key,
        content_type=content_type,
        size=size,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "size": attachment.size,
        "created_at": attachment.created_at.isoformat(),
    }


@router.get("/entity/{entity_type}/{entity_id}")
async def list_attachments(
    entity_type: str,
    entity_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all attachments for a given entity."""
    query = select(Attachment).where(
        Attachment.entity_type == entity_type,
        Attachment.entity_id == entity_id,
        Attachment.user_id == current_user.id,
    )
    if current_user.role == RoleEnum.admin:
        query = select(Attachment).where(
            Attachment.entity_type == entity_type,
            Attachment.entity_id == entity_id,
        )

    result = await db.execute(query)
    attachments = result.scalars().all()

    return [
        {
            "id": a.id,
            "filename": a.filename,
            "content_type": a.content_type,
            "size": a.size,
            "created_at": a.created_at.isoformat(),
        }
        for a in attachments
    ]


@router.get("/{attachment_id}/url")
async def get_presigned_url(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a pre-signed URL for downloading an attachment."""
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    attachment = result.scalar_one_or_none()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if attachment.user_id != current_user.id and current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    url = await s3_service.generate_presigned_url(attachment.s3_key, expires=3600)
    return {
        "url": url,
        "expires_in": 3600,
        "filename": attachment.filename,
    }


@router.delete("/{attachment_id}", status_code=204)
async def delete_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an attachment and its file from S3."""
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    attachment = result.scalar_one_or_none()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if attachment.user_id != current_user.id and current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    await s3_service.delete_file(attachment.s3_key)
    await db.delete(attachment)
    await db.commit()
