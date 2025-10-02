from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pathlib import Path
import uuid
from datetime import datetime
import os

from ....models.customer import Customer as CustomerModel
from ....models.customer_attachment import CustomerAttachment as CustomerAttachmentModel
from ....models.user import User
from ....models.organization import Organization
from ...deps import get_current_active_user, get_current_organization
from ...deps_tenant import get_tenant_db
from ....schemas.customer_attachment import CustomerAttachment, CustomerAttachmentList
from ....core.config import settings

router = APIRouter()


async def _get_customer_or_404(db: AsyncSession, org_id: str, customer_id: str) -> CustomerModel:
    result = await db.execute(
        select(CustomerModel).where(
            and_(
                CustomerModel.id == customer_id,
                CustomerModel.organization_id == org_id
            )
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.post("/{customer_id}/attachments", response_model=CustomerAttachment, status_code=status.HTTP_201_CREATED)
async def upload_customer_attachment(
    customer_id: str,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # comma-separated
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Upload an attachment for a customer and persist metadata"""

    # Validate customer
    await _get_customer_or_404(db, current_org.id, customer_id)

    # Prepare upload directory
    upload_dir = Path(settings.UPLOAD_DIR) / current_org.id / "customers" / customer_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix if file.filename else ""
    filename = f"{file_id}{ext}"
    path = upload_dir / filename

    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    # Build attachment row
    attachment = CustomerAttachmentModel(
        id=file_id,
        customer_id=customer_id,
        organization_id=current_org.id,
        original_filename=file.filename,
        content_type=file.content_type,
        size=len(content) if content is not None else None,
        storage_path=str(path),
        uploaded_by=current_user.id,
        description=description or None,
        tags=[t.strip() for t in tags.split(",")] if tags else [],
    )

    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


@router.get("/{customer_id}/attachments", response_model=CustomerAttachmentList)
async def list_customer_attachments(
    customer_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    await _get_customer_or_404(db, current_org.id, customer_id)

    result = await db.execute(
        select(CustomerAttachmentModel).where(
            and_(
                CustomerAttachmentModel.customer_id == customer_id,
                CustomerAttachmentModel.organization_id == current_org.id
            )
        )
    )
    items = result.scalars().all()
    return {"attachments": items}


@router.delete("/{customer_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer_attachment(
    customer_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> None:
    await _get_customer_or_404(db, current_org.id, customer_id)

    result = await db.execute(
        select(CustomerAttachmentModel).where(
            and_(
                CustomerAttachmentModel.id == attachment_id,
                CustomerAttachmentModel.customer_id == customer_id,
                CustomerAttachmentModel.organization_id == current_org.id
            )
        )
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    # Attempt to delete file from disk
    try:
        if att.storage_path and os.path.exists(att.storage_path):
            os.remove(att.storage_path)
    except Exception:
        pass

    await db.delete(att)
    await db.commit()
    return None
