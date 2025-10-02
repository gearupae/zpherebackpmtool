from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.orm import selectinload
import uuid

from ....db.database import get_db
from ...deps_tenant import get_tenant_db
from ....models.customer import Customer as CustomerModel
from ....models.customer_attachment import CustomerAttachment as CustomerAttachmentModel
from ....models.user import User
from ....models.project import Project
from sqlalchemy.exc import SQLAlchemyError
from ....schemas.customer import (
    Customer, CustomerCreate, CustomerUpdate, CustomerList, CustomerStats,
    CustomerAttachment, CustomerAttachmentUpdate
)
from ...deps import get_current_active_user
from ...deps_tenant import get_tenant_db
from ....core.config import settings
from pathlib import Path
import uuid
from fastapi.responses import FileResponse

router = APIRouter()


def _serialize_attachment(a: CustomerAttachmentModel) -> dict:
    return {
        "id": a.id,
        "customer_id": a.customer_id,
        "original_filename": a.original_filename,
        "content_type": a.content_type,
        "size": a.size,
        "storage_path": a.storage_path,
        "uploaded_by": a.uploaded_by,
        "description": a.description,
        "tags": a.tags or [],
        "created_at": a.created_at,
        "updated_at": a.updated_at,
    }


def _serialize_customer(c: CustomerModel) -> dict:
    return {
        "id": c.id,
        "organization_id": c.organization_id,
        "first_name": c.first_name,
        "last_name": c.last_name,
        "email": c.email,
        "phone": c.phone,
        "company_name": c.company_name,
        "company_website": c.company_website,
        "job_title": c.job_title,
        "address_line_1": c.address_line_1,
        "address_line_2": c.address_line_2,
        "city": c.city,
        "state": c.state,
        "postal_code": c.postal_code,
        "country": c.country,
        "customer_type": c.customer_type,
        "source": c.source,
        "credit_limit": c.credit_limit,
        "payment_terms": c.payment_terms,
        "notes": c.notes,
        "tags": c.tags or [],
        "custom_fields": c.custom_fields or {},
        "is_active": c.is_active,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
        "full_name": c.full_name,
        "display_name": c.display_name,
        "attachments": [_serialize_attachment(a) for a in getattr(c, "attachments", [])],
    }


@router.get("/", response_model=CustomerList)
async def get_customers(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    customer_type: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Any:
    """Get customers with pagination and filtering"""
    
    # Build base query with organization filtering
    query = select(CustomerModel).where(CustomerModel.organization_id == current_user.organization_id)
    
    # Apply filters
    if search:
        search_filter = or_(
            CustomerModel.first_name.ilike(f"%{search}%"),
            CustomerModel.last_name.ilike(f"%{search}%"),
            CustomerModel.company_name.ilike(f"%{search}%"),
            CustomerModel.email.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    if customer_type:
        query = query.where(CustomerModel.customer_type == customer_type)
    
    if is_active is not None:
        query = query.where(CustomerModel.is_active == is_active)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.offset((page - 1) * size).limit(size)
    query = query.order_by(CustomerModel.created_at.desc())
    
    # Preload attachments to avoid async lazy-load during serialization
    query = query.options(selectinload(CustomerModel.attachments))
    
    # Execute query
    result = await db.execute(query)
    customers = result.scalars().unique().all()
    
    # Calculate pagination info
    pages = (total + size - 1) // size
    
    # Serialize to plain dicts and validate against schema
    serialized = [_serialize_customer(c) for c in customers]
    return CustomerList(
        customers=[Customer.model_validate(sc) for sc in serialized],
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/stats", response_model=CustomerStats)
async def get_customer_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get customer statistics"""
    
    # Get customer counts by type
    stats_query = select(
        func.count().label("total"),
        func.coalesce(func.sum(case((CustomerModel.is_active == True, 1), else_=0)), 0).label("active"),
        func.coalesce(func.sum(case((CustomerModel.customer_type == "prospect", 1), else_=0)), 0).label("prospects"),
        func.coalesce(func.sum(case((CustomerModel.customer_type == "client", 1), else_=0)), 0).label("clients"),
        func.coalesce(func.sum(case((CustomerModel.customer_type == "lead", 1), else_=0)), 0).label("leads"),
        func.coalesce(func.sum(case((CustomerModel.is_active == False, 1), else_=0)), 0).label("inactive")
    ).where(CustomerModel.organization_id == current_user.organization_id)
    
    stats_result = await db.execute(stats_query)
    stats = stats_result.first()
    
    # Get project count and revenue
    try:
        # Try to get project stats
        project_query = select(
            func.count().label("total_projects"),
            func.coalesce(func.sum(Project.budget), 0).label("total_revenue")
        ).join(CustomerModel).where(
            Project.customer_id == CustomerModel.id
        )
        
        project_result = await db.execute(project_query)
        project_stats = project_result.first()
    except SQLAlchemyError as e:
        # Handle case where Project table might not exist in tenant DB
        # or there's a schema mismatch
        print(f"Error getting project stats: {str(e)}")
        project_stats = type('ProjectStats', (), {'total_projects': 0, 'total_revenue': 0})
    
    return CustomerStats(
        total_customers=stats.total or 0,
        active_customers=stats.active or 0,
        prospects=stats.prospects or 0,
        clients=stats.clients or 0,
        leads=stats.leads or 0,
        inactive_customers=stats.inactive or 0,
        total_projects=project_stats.total_projects or 0,
        total_revenue=project_stats.total_revenue or 0
    )


@router.get("/{customer_id}", response_model=Customer)
async def get_customer(
    customer_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific customer by ID"""
    
    result = await db.execute(
        select(CustomerModel)
        .options(selectinload(CustomerModel.attachments))
        .where(
            and_(CustomerModel.id == customer_id, CustomerModel.organization_id == current_user.organization_id)
        )
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    return Customer.model_validate(_serialize_customer(customer))


@router.post("/", response_model=Customer, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new customer"""
    
    # Check permissions for creating customers
    from ....models.user import Permission
    if not current_user.has_permission(Permission.CREATE_CUSTOMER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create customers"
        )
    
    # Check if email already exists in organization
    existing_customer = await db.execute(
        select(CustomerModel).where(
            and_(CustomerModel.email == customer_data.email, CustomerModel.organization_id == current_user.organization_id)
        )
    )
    if existing_customer.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer with this email already exists"
        )
    
    # Create customer with organization_id
    customer = CustomerModel(
        id=str(uuid.uuid4()),
        organization_id=current_user.organization_id,
        **customer_data.model_dump()
    )
    
    db.add(customer)
    await db.commit()
    # Ensure relationships are loaded to avoid lazy-load during response serialization
    try:
        await db.refresh(customer, ["attachments"])  # preload attachments relation
    except Exception:
        # Non-fatal; proceed
        await db.refresh(customer)
    
    return Customer.model_validate(_serialize_customer(customer))


@router.put("/{customer_id}", response_model=Customer)
async def update_customer(
    customer_id: str,
    customer_data: CustomerUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a customer"""
    
    # Get customer
    result = await db.execute(
        select(CustomerModel).where(
            CustomerModel.id == customer_id
        )
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Check email uniqueness if changing
    if customer_data.email and customer_data.email != customer.email:
        existing_customer = await db.execute(
            select(CustomerModel).where(
                and_(
                    CustomerModel.email == customer_data.email,
                    CustomerModel.id != customer_id
                )
            )
        )
        if existing_customer.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer with this email already exists"
            )
    
    # Update customer
    update_data = customer_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)
    
    await db.commit()
    await db.refresh(customer)
    
    return Customer.model_validate(_serialize_customer(customer))


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_customer(
    customer_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a customer (soft delete by setting is_active to False)"""
    
    # Get customer
    result = await db.execute(
        select(CustomerModel).where(
            CustomerModel.id == customer_id
        )
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Check if customer has active projects
    project_query = select(func.count()).where(
        and_(
            Project.customer_id == customer_id,
            Project.status.in_(["planning", "active", "on_hold"])
        )
    )
    project_result = await db.execute(project_query)
    active_projects = project_result.scalar()
    
    if active_projects > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete customer with active projects"
        )
    
    # Soft delete
    customer.is_active = False
    await db.commit()
    return None




@router.put("/attachments/{attachment_id}", response_model=CustomerAttachment)
async def update_customer_attachment(
    attachment_id: str,
    update: CustomerAttachmentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update attachment metadata (description, tags)."""
    result = await db.execute(
        select(CustomerAttachmentModel).where(
            and_(CustomerAttachmentModel.id == attachment_id, CustomerAttachmentModel.organization_id == current_user.organization_id)
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    data = update.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(attachment, k, v)
    await db.commit()
    await db.refresh(attachment)
    return attachment


@router.delete("/attachments/{attachment_id}", status_code=204, response_class=Response)
async def delete_customer_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Response:
    """Delete an attachment file and metadata."""
    result = await db.execute(
        select(CustomerAttachmentModel).where(
            and_(CustomerAttachmentModel.id == attachment_id, CustomerAttachmentModel.organization_id == current_user.organization_id)
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Attempt to delete file from disk
    try:
        if attachment.storage_path:
            path = Path(attachment.storage_path)
            if path.exists():
                path.unlink()
    except Exception:
        # Non-fatal: continue to delete metadata
        pass

    await db.delete(attachment)
    await db.commit()
    return Response(status_code=204)


@router.get("/attachments/{attachment_id}/download")
async def download_customer_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Download an attachment as a file (Content-Disposition: attachment)."""
    result = await db.execute(
        select(CustomerAttachmentModel).where(
            and_(CustomerAttachmentModel.id == attachment_id, CustomerAttachmentModel.organization_id == current_user.organization_id)
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if not attachment.storage_path or not Path(attachment.storage_path).exists():
        raise HTTPException(status_code=404, detail="File not found on server")
    filename = attachment.original_filename or Path(attachment.storage_path).name
    return FileResponse(
        path=attachment.storage_path,
        media_type=attachment.content_type or "application/octet-stream",
        filename=filename
    )


@router.get("/attachments/{attachment_id}/preview")
async def preview_customer_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Preview an attachment inline (Content-Disposition: inline)."""
    result = await db.execute(
        select(CustomerAttachmentModel).where(
            and_(CustomerAttachmentModel.id == attachment_id, CustomerAttachmentModel.organization_id == current_user.organization_id)
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if not attachment.storage_path or not Path(attachment.storage_path).exists():
        raise HTTPException(status_code=404, detail="File not found on server")
    filename = attachment.original_filename or Path(attachment.storage_path).name
    response = FileResponse(
        path=attachment.storage_path,
        media_type=attachment.content_type or "application/octet-stream",
        filename=filename
    )
    # Force inline preview
    response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
