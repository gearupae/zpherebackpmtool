"""
API endpoints for delivery note management with partial delivery tracking
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, case
from sqlalchemy.orm import selectinload
import uuid
from datetime import datetime

from ...deps_tenant import get_tenant_db
from ....models.delivery_note import DeliveryNote as DeliveryNoteModel, DeliveryNoteItem as DeliveryNoteItemModel, DeliveryStatus
from ....models.project_invoice import ProjectInvoice as InvoiceModel
from ....models.user import User
from ....schemas.delivery_note import (
    DeliveryNote, DeliveryNoteCreate, DeliveryNoteUpdate, DeliveryNoteList, 
    DeliveryNoteStats, InvoiceDeliveryStatus
)
from ...deps import get_current_active_user, require_manager

router = APIRouter()


def generate_delivery_note_number() -> str:
    """Generate a unique delivery note number"""
    now = datetime.now()
    return f"DN-{now.year}-{now.month:02d}-{now.day:02d}-{uuid.uuid4().hex[:6].upper()}"


@router.get("/", response_model=DeliveryNoteList)
async def get_delivery_notes(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[DeliveryStatus] = None,
    invoice_id: Optional[str] = None,
) -> Any:
    """Get delivery notes with pagination and filtering"""
    
    # Build base query
    query = select(DeliveryNoteModel).options(
        selectinload(DeliveryNoteModel.items)
    ).where(
        DeliveryNoteModel.organization_id == current_user.organization_id
    )
    
    # Apply filters
    if search:
        query = query.where(
            DeliveryNoteModel.delivery_note_number.ilike(f"%{search}%")
        )
    
    if status:
        query = query.where(DeliveryNoteModel.status == status)
    
    if invoice_id:
        query = query.where(DeliveryNoteModel.invoice_id == invoice_id)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and ordering
    query = query.offset((page - 1) * size).limit(size)
    query = query.order_by(DeliveryNoteModel.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    delivery_notes = result.scalars().all()
    
    # Calculate pagination info
    pages = (total + size - 1) // size
    
    return DeliveryNoteList(
        delivery_notes=delivery_notes,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/{delivery_note_id}", response_model=DeliveryNote)
async def get_delivery_note(
    delivery_note_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific delivery note by ID"""
    
    query = select(DeliveryNoteModel).options(
        selectinload(DeliveryNoteModel.items)
    ).where(
        and_(
            DeliveryNoteModel.id == delivery_note_id,
            DeliveryNoteModel.organization_id == current_user.organization_id
        )
    )
    
    result = await db.execute(query)
    delivery_note = result.scalar_one_or_none()
    
    if not delivery_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery note not found"
        )
    
    return delivery_note


@router.post("/", response_model=DeliveryNote, status_code=status.HTTP_201_CREATED)
async def create_delivery_note(
    delivery_note_data: DeliveryNoteCreate,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new delivery note"""
    
    # Verify invoice exists and user has access
    invoice_result = await db.execute(
        select(InvoiceModel).where(
            and_(
                InvoiceModel.id == delivery_note_data.invoice_id,
                InvoiceModel.organization_id == current_user.organization_id
            )
        )
    )
    invoice = invoice_result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Generate delivery note number
    delivery_note_number = generate_delivery_note_number()
    
    # Create delivery note
    delivery_note = DeliveryNoteModel(
        id=str(uuid.uuid4()),
        delivery_note_number=delivery_note_number,
        organization_id=current_user.organization_id,
        invoice_id=delivery_note_data.invoice_id,
        created_by_id=current_user.id,
        delivery_date=delivery_note_data.delivery_date,
        delivery_address=delivery_note_data.delivery_address,
        delivery_contact_name=delivery_note_data.delivery_contact_name,
        delivery_contact_phone=delivery_note_data.delivery_contact_phone,
        driver_name=delivery_note_data.driver_name,
        vehicle_info=delivery_note_data.vehicle_info,
        tracking_number=delivery_note_data.tracking_number,
        notes=delivery_note_data.notes,
        status=DeliveryStatus.DRAFT
    )
    
    db.add(delivery_note)
    await db.flush()
    
    # Create delivery note items
    for item_data in delivery_note_data.items:
        # Calculate remaining quantity (for first delivery, it's the full ordered quantity)
        remaining_quantity = item_data.quantity_ordered - item_data.quantity_delivered
        
        delivery_item = DeliveryNoteItemModel(
            id=str(uuid.uuid4()),
            delivery_note_id=delivery_note.id,
            item_id=item_data.item_id,
            invoice_item_reference=item_data.invoice_item_reference,
            item_name=item_data.item_name,
            description=item_data.description,
            quantity_ordered=item_data.quantity_ordered,
            quantity_delivered=item_data.quantity_delivered,
            quantity_remaining=remaining_quantity,
            unit_price=item_data.unit_price
        )
        db.add(delivery_item)
    
    # Calculate totals
    delivery_note.calculate_totals()
    
    await db.commit()
    await db.refresh(delivery_note)
    
    # Load items for response
    await db.refresh(delivery_note, ["items"])
    
    return delivery_note


@router.put("/{delivery_note_id}", response_model=DeliveryNote)
async def update_delivery_note(
    delivery_note_id: str,
    delivery_note_data: DeliveryNoteUpdate,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a delivery note"""
    
    # Get existing delivery note
    query = select(DeliveryNoteModel).options(
        selectinload(DeliveryNoteModel.items)
    ).where(
        and_(
            DeliveryNoteModel.id == delivery_note_id,
            DeliveryNoteModel.organization_id == current_user.organization_id
        )
    )
    
    result = await db.execute(query)
    delivery_note = result.scalar_one_or_none()
    
    if not delivery_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery note not found"
        )
    
    # Update fields
    update_data = delivery_note_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if field != "items" and hasattr(delivery_note, field):
            setattr(delivery_note, field, value)
    
    # Update items if provided
    if delivery_note_data.items is not None:
        # For simplicity, we'll update quantities for existing items
        # In a more complex scenario, you might want to handle item additions/removals
        for item_update in delivery_note_data.items:
            # Find matching item (this is simplified - you might want better matching logic)
            for existing_item in delivery_note.items:
                if (item_update.item_name and existing_item.item_name == item_update.item_name):
                    if item_update.quantity_delivered is not None:
                        existing_item.quantity_delivered = item_update.quantity_delivered
                        existing_item.update_remaining_quantity()
                    break
    
    # Recalculate totals
    delivery_note.calculate_totals()
    
    await db.commit()
    await db.refresh(delivery_note)
    
    return delivery_note


@router.patch("/{delivery_note_id}/status")
async def update_delivery_note_status(
    delivery_note_id: str,
    status_data: dict,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update delivery note status"""
    
    # Get existing delivery note
    query = select(DeliveryNoteModel).where(
        and_(
            DeliveryNoteModel.id == delivery_note_id,
            DeliveryNoteModel.organization_id == current_user.organization_id
        )
    )
    
    result = await db.execute(query)
    delivery_note = result.scalar_one_or_none()
    
    if not delivery_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery note not found"
        )
    
    # Update status
    new_status = status_data.get("status")
    if new_status and new_status in [status.value for status in DeliveryStatus]:
        delivery_note.status = DeliveryStatus(new_status)
        await db.commit()
        return {"message": "Status updated successfully", "status": delivery_note.status}
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid status"
    )


@router.delete("/{delivery_note_id}")
async def delete_delivery_note(
    delivery_note_id: str,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Delete a delivery note"""
    
    # Get existing delivery note
    query = select(DeliveryNoteModel).where(
        and_(
            DeliveryNoteModel.id == delivery_note_id,
            DeliveryNoteModel.organization_id == current_user.organization_id
        )
    )
    
    result = await db.execute(query)
    delivery_note = result.scalar_one_or_none()
    
    if not delivery_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery note not found"
        )
    
    await db.delete(delivery_note)
    await db.commit()
    
    return {"message": "Delivery note deleted successfully"}


@router.get("/stats", response_model=DeliveryNoteStats)
async def get_delivery_note_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get delivery note statistics"""
    
    query = select(
        func.count().label("total_delivery_notes"),
        func.coalesce(func.sum(case((DeliveryNoteModel.status == DeliveryStatus.DRAFT, 1), else_=0)), 0).label("draft_notes"),
        func.coalesce(func.sum(case((DeliveryNoteModel.status == DeliveryStatus.IN_TRANSIT, 1), else_=0)), 0).label("in_transit_notes"),
        func.coalesce(func.sum(case((DeliveryNoteModel.status == DeliveryStatus.DELIVERED, 1), else_=0)), 0).label("delivered_notes"),
        func.coalesce(func.sum(case((DeliveryNoteModel.status == DeliveryStatus.CANCELLED, 1), else_=0)), 0).label("cancelled_notes"),
    ).where(
        DeliveryNoteModel.organization_id == current_user.organization_id
    )
    
    result = await db.execute(query)
    stats = result.first()
    
    # Calculate completion rate
    completion_rate = 0
    if stats.total_delivery_notes > 0:
        completion_rate = (stats.delivered_notes / stats.total_delivery_notes) * 100
    
    return DeliveryNoteStats(
        total_delivery_notes=stats.total_delivery_notes,
        draft_notes=stats.draft_notes,
        in_transit_notes=stats.in_transit_notes,
        delivered_notes=stats.delivered_notes,
        cancelled_notes=stats.cancelled_notes,
        completion_rate=completion_rate
    )


@router.get("/invoice/{invoice_id}/delivery-status", response_model=InvoiceDeliveryStatus)
async def get_invoice_delivery_status(
    invoice_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get delivery status summary for a specific invoice"""
    
    # Get invoice
    invoice_result = await db.execute(
        select(InvoiceModel).where(
            and_(
                InvoiceModel.id == invoice_id,
                InvoiceModel.organization_id == current_user.organization_id
            )
        )
    )
    invoice = invoice_result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Get delivery notes for this invoice
    delivery_notes_result = await db.execute(
        select(DeliveryNoteModel).options(
            selectinload(DeliveryNoteModel.items)
        ).where(
            DeliveryNoteModel.invoice_id == invoice_id
        ).order_by(DeliveryNoteModel.delivery_date.desc())
    )
    delivery_notes = delivery_notes_result.scalars().all()
    
    # Calculate delivery status
    invoice_items = invoice.items or []
    total_items = len(invoice_items)
    items_with_deliveries = 0
    total_ordered_quantity = 0
    total_delivered_quantity = 0
    
    # Calculate totals from invoice items and delivery notes
    for invoice_item in invoice_items:
        quantity_ordered = invoice_item.get('quantity', 0)
        total_ordered_quantity += quantity_ordered
        
        # Find delivered quantities for this item across all delivery notes
        delivered_for_item = 0
        for delivery_note in delivery_notes:
            for delivery_item in delivery_note.items:
                if delivery_item.item_name == invoice_item.get('description', ''):
                    delivered_for_item += delivery_item.quantity_delivered
        
        total_delivered_quantity += delivered_for_item
        if delivered_for_item > 0:
            items_with_deliveries += 1
    
    remaining_quantity = max(0, total_ordered_quantity - total_delivered_quantity)
    delivery_percentage = (total_delivered_quantity / total_ordered_quantity * 100) if total_ordered_quantity > 0 else 0
    is_fully_delivered = remaining_quantity == 0 and total_ordered_quantity > 0
    
    latest_delivery_date = delivery_notes[0].delivery_date if delivery_notes else None
    
    return InvoiceDeliveryStatus(
        invoice_id=invoice_id,
        invoice_number=invoice.invoice_number,
        total_items=total_items,
        items_with_deliveries=items_with_deliveries,
        total_ordered_quantity=total_ordered_quantity,
        total_delivered_quantity=total_delivered_quantity,
        remaining_quantity=remaining_quantity,
        delivery_percentage=delivery_percentage,
        is_fully_delivered=is_fully_delivered,
        delivery_notes_count=len(delivery_notes),
        latest_delivery_date=latest_delivery_date
    )
