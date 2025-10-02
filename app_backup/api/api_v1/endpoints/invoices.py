from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.orm import selectinload
import uuid
from datetime import datetime, timedelta

from ....db.database import get_db
from ....models.project_invoice import ProjectInvoice as InvoiceModel, InvoiceStatus, InvoiceType
from ....models.user import User
from ....models.project import Project
from ....models.customer import Customer
from ....schemas.project_invoice import (
    ProjectInvoice, ProjectInvoiceCreate, ProjectInvoiceUpdate, ProjectInvoiceList, InvoiceStats
)
from ...deps import get_current_active_user, require_manager

router = APIRouter()


@router.get("/", response_model=ProjectInvoiceList)
async def get_invoices(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[InvoiceStatus] = None,
    invoice_type: Optional[InvoiceType] = None,
    project_id: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> Any:
    """Get invoices with pagination and filtering"""
    
    # Build base query
    query = select(InvoiceModel).where(
        InvoiceModel.organization_id == current_user.organization_id
    )
    
    # Apply filters
    if search:
        search_filter = or_(
            InvoiceModel.title.ilike(f"%{search}%"),
            InvoiceModel.invoice_number.ilike(f"%{search}%"),
            InvoiceModel.description.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    if status:
        query = query.where(InvoiceModel.status == status)
    
    if invoice_type:
        query = query.where(InvoiceModel.invoice_type == invoice_type)
    
    if project_id:
        query = query.where(InvoiceModel.project_id == project_id)
    
    if customer_id:
        query = query.where(InvoiceModel.customer_id == customer_id)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and ordering
    query = query.offset((page - 1) * size).limit(size)
    query = query.order_by(InvoiceModel.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    invoices = result.scalars().all()
    
    # Calculate pagination info
    pages = (total + size - 1) // size
    
    return ProjectInvoiceList(
        invoices=invoices,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/stats", response_model=InvoiceStats)
async def get_invoice_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get invoice statistics"""
    
    # Get invoice counts and amounts by status
    stats_query = select(
        func.count().label("total_invoices"),
        func.coalesce(func.sum(case((InvoiceModel.status == InvoiceStatus.DRAFT, 1), else_=0)), 0).label("draft_invoices"),
        func.coalesce(func.sum(case((InvoiceModel.status == InvoiceStatus.SENT, 1), else_=0)), 0).label("sent_invoices"),
        func.coalesce(func.sum(case((InvoiceModel.status == InvoiceStatus.PENDING, 1), else_=0)), 0).label("pending_invoices"),
        func.coalesce(func.sum(case((InvoiceModel.status == InvoiceStatus.PAID, 1), else_=0)), 0).label("paid_invoices"),
        func.coalesce(func.sum(case((InvoiceModel.status == InvoiceStatus.OVERDUE, 1), else_=0)), 0).label("overdue_invoices"),
        func.coalesce(func.sum(InvoiceModel.total_amount), 0).label("total_amount"),
        func.coalesce(func.sum(InvoiceModel.amount_paid), 0).label("total_paid"),
        func.coalesce(func.sum(InvoiceModel.balance_due), 0).label("total_outstanding"),
        func.coalesce(func.sum(case((InvoiceModel.status == InvoiceStatus.OVERDUE, InvoiceModel.balance_due), else_=0)), 0).label("overdue_amount")
    ).where(InvoiceModel.organization_id == current_user.organization_id)
    
    stats_result = await db.execute(stats_query)
    stats = stats_result.first()
    
    # Calculate average payment time (simplified)
    avg_payment_query = select(
        func.avg(func.extract('day', InvoiceModel.paid_date - InvoiceModel.sent_date)).label("avg_days")
    ).where(
        and_(
            InvoiceModel.organization_id == current_user.organization_id,
            InvoiceModel.status == InvoiceStatus.PAID,
            InvoiceModel.sent_date.is_not(None),
            InvoiceModel.paid_date.is_not(None)
        )
    )
    
    avg_result = await db.execute(avg_payment_query)
    avg_payment_time = avg_result.scalar() or 0
    
    return InvoiceStats(
        total_invoices=stats.total_invoices or 0,
        draft_invoices=stats.draft_invoices or 0,
        sent_invoices=stats.sent_invoices or 0,
        pending_invoices=stats.pending_invoices or 0,
        paid_invoices=stats.paid_invoices or 0,
        overdue_invoices=stats.overdue_invoices or 0,
        total_amount=stats.total_amount or 0,
        total_paid=stats.total_paid or 0,
        total_outstanding=stats.total_outstanding or 0,
        overdue_amount=stats.overdue_amount or 0,
        average_payment_time=int(avg_payment_time)
    )


@router.get("/{invoice_id}", response_model=ProjectInvoice)
async def get_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get a specific invoice by ID"""
    
    result = await db.execute(
        select(InvoiceModel).where(
            and_(
                InvoiceModel.id == invoice_id,
                InvoiceModel.organization_id == current_user.organization_id
            )
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return invoice


@router.post("/", response_model=ProjectInvoice, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice_data: ProjectInvoiceCreate,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new invoice"""
    
    # Verify project exists and user has access
    project_result = await db.execute(
        select(Project).where(
            and_(
                Project.id == invoice_data.project_id,
                Project.organization_id == current_user.organization_id
            )
        )
    )
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Verify customer exists and is in same organization
    customer_result = await db.execute(
        select(Customer).where(
            and_(
                Customer.id == invoice_data.customer_id,
                Customer.organization_id == current_user.organization_id
            )
        )
    )
    customer = customer_result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Generate invoice number
    year = datetime.now().year
    count_result = await db.execute(
        select(func.count()).where(
            and_(
                InvoiceModel.organization_id == current_user.organization_id,
                func.extract('year', InvoiceModel.created_at) == year
            )
        )
    )
    invoice_count = count_result.scalar() + 1
    invoice_number = f"INV-{year}-{invoice_count:04d}"
    
    # Calculate amounts from items
    subtotal = sum(item.quantity * item.unit_price for item in invoice_data.items)
    tax_amount = sum(
        (item.quantity * item.unit_price * item.tax_rate) // 100 
        for item in invoice_data.items
    )
    discount_amount = sum(
        (item.quantity * item.unit_price * item.discount_rate) // 100 
        for item in invoice_data.items
    )
    total_amount = subtotal + tax_amount - discount_amount
    
    # Calculate due date
    due_date = None
    if invoice_data.invoice_date:
        invoice_date = invoice_data.invoice_date
        if customer.payment_terms == "net_15":
            due_date = invoice_date + timedelta(days=15)
        elif customer.payment_terms == "net_30":
            due_date = invoice_date + timedelta(days=30)
        elif customer.payment_terms == "net_60":
            due_date = invoice_date + timedelta(days=60)
        else:
            due_date = invoice_date + timedelta(days=30)  # Default
    
    # Create invoice
    invoice = InvoiceModel(
        id=str(uuid.uuid4()),
        invoice_number=invoice_number,
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
        project_id=invoice_data.project_id,
        customer_id=invoice_data.customer_id,
        title=invoice_data.title,
        description=invoice_data.description,
        invoice_type=invoice_data.invoice_type,
        status=InvoiceStatus.DRAFT,
        currency=invoice_data.currency,
        exchange_rate=invoice_data.exchange_rate,
        payment_terms=invoice_data.payment_terms,
        invoice_date=invoice_data.invoice_date,
        due_date=due_date,
        subtotal=subtotal,
        tax_amount=tax_amount,
        discount_amount=discount_amount,
        total_amount=total_amount,
        amount_paid=0,
        balance_due=total_amount,
        notes=invoice_data.notes,
        terms_and_conditions=invoice_data.terms_and_conditions,
        is_recurring=invoice_data.is_recurring,
        recurring_interval=invoice_data.recurring_interval,
        next_invoice_date=invoice_data.next_invoice_date,
        tags=invoice_data.tags,
        custom_fields=invoice_data.custom_fields,
        late_fees=0,
        reminder_sent_count=0
    )
    
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    
    return invoice


@router.put("/{invoice_id}", response_model=ProjectInvoice)
async def update_invoice(
    invoice_id: str,
    invoice_data: ProjectInvoiceUpdate,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update an invoice"""
    
    # Get invoice
    result = await db.execute(
        select(InvoiceModel).where(
            and_(
                InvoiceModel.id == invoice_id,
                InvoiceModel.organization_id == current_user.organization_id
            )
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Don't allow updating paid invoices
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update paid invoice"
        )
    
    # Update invoice fields
    update_data = invoice_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(invoice, field, value)
    
    await db.commit()
    await db.refresh(invoice)
    
    return invoice


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: str,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Delete an invoice (only drafts can be deleted)"""
    
    # Get invoice
    result = await db.execute(
        select(InvoiceModel).where(
            and_(
                InvoiceModel.id == invoice_id,
                InvoiceModel.organization_id == current_user.organization_id
            )
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Only allow deleting draft invoices
    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft invoices can be deleted"
        )
    
    await db.delete(invoice)
    await db.commit()


@router.post("/{invoice_id}/send")
async def send_invoice(
    invoice_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Send invoice to customer"""
    
    # Get invoice with customer info
    result = await db.execute(
        select(InvoiceModel).options(
            selectinload(InvoiceModel.customer)
        ).where(
            and_(
                InvoiceModel.id == invoice_id,
                InvoiceModel.organization_id == current_user.organization_id
            )
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    if invoice.status not in [InvoiceStatus.DRAFT, InvoiceStatus.PENDING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice has already been sent or paid"
        )
    
    # Update invoice status
    invoice.status = InvoiceStatus.SENT
    invoice.sent_date = datetime.utcnow()
    
    await db.commit()
    
    # Add background task to send email (placeholder)
    background_tasks.add_task(send_invoice_email, invoice.id, invoice.customer.email)
    
    return {"message": "Invoice sent successfully", "sent_date": invoice.sent_date}


@router.post("/{invoice_id}/mark-paid")
async def mark_invoice_paid(
    invoice_id: str,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Mark invoice as paid"""
    
    # Get invoice
    result = await db.execute(
        select(InvoiceModel).where(
            and_(
                InvoiceModel.id == invoice_id,
                InvoiceModel.organization_id == current_user.organization_id
            )
        )
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is already paid"
        )
    
    # Update invoice
    invoice.status = InvoiceStatus.PAID
    invoice.amount_paid = invoice.total_amount
    invoice.balance_due = 0
    invoice.paid_date = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Invoice marked as paid", "paid_date": invoice.paid_date}


async def send_invoice_email(invoice_id: str, customer_email: str):
    """Background task to send invoice email (placeholder)"""
    # This would integrate with your email service
    print(f"Sending invoice {invoice_id} to {customer_email}")
    # TODO: Implement actual email sending
    pass
