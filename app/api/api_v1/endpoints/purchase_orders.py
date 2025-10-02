from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional, Any
from datetime import datetime, date
from ...deps import get_current_active_user as get_current_user
from ....models.user import User
from ....models.vendor import Vendor
from ....models.purchase_order import PurchaseOrder, PurchaseOrderItem, ItemUnit
from ....models.item import Item as ItemModel
from ....models.project import Project as ProjectModel
from ....models.customer import Customer as CustomerModel
from ....models.organization import Organization
from ....services.pdf_service import PDFService
from ....db.database import get_db
from ...deps_tenant import get_tenant_db
from ....schemas.purchase_order import (
    PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderResponse, PurchaseOrderListResponse,
    PurchaseOrderStats, PurchaseOrderStatusUpdate, PurchaseOrderItemCreate, PurchaseOrderItemUpdate,
    PurchaseOrderItemResponse
)
import uuid
import io

router = APIRouter()


def generate_po_number() -> str:
    """Generate a unique PO number"""
    from datetime import datetime
    now = datetime.now()
    return f"PO-{now.year}-{now.month:02d}-{now.day:02d}-{uuid.uuid4().hex[:6].upper()}"


@router.get("/", response_model=PurchaseOrderListResponse)
async def get_purchase_orders(
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    vendor_id: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    department: Optional[str] = Query(None)
):
    """Get list of purchase orders for the current organization"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    # Build base query with vendor information
    query = select(PurchaseOrder).options(
        selectinload(PurchaseOrder.vendor),
        selectinload(PurchaseOrder.items)
    ).where(PurchaseOrder.organization_id == current_user.organization_id)
    
    # Apply filters
    if search:
        search_filter = or_(
            PurchaseOrder.po_number.ilike(f"%{search}%"),
            PurchaseOrder.requested_by.ilike(f"%{search}%"),
            PurchaseOrder.department.ilike(f"%{search}%"),
            PurchaseOrder.notes.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    if status:
        query = query.where(PurchaseOrder.status == status)
    
    if vendor_id:
        query = query.where(PurchaseOrder.vendor_id == vendor_id)
    
    if priority:
        query = query.where(PurchaseOrder.priority == priority)
    
    if department:
        query = query.where(PurchaseOrder.department.ilike(f"%{department}%"))
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and get results
    query = query.offset((page - 1) * size).limit(size).order_by(PurchaseOrder.created_at.desc())
    result = await db.execute(query)
    purchase_orders = result.scalars().all()
    
    # Convert to response format with vendor names
    po_responses = []
    for po in purchase_orders:
        po_dict = po.__dict__.copy()
        po_dict['vendor_name'] = po.vendor.name if po.vendor else None
        po_dict['items'] = [PurchaseOrderItemResponse.model_validate(item) for item in po.items]
        po_responses.append(PurchaseOrderResponse(**po_dict))
    
    return PurchaseOrderListResponse(
        purchase_orders=po_responses,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.post("/", response_model=PurchaseOrderResponse)
async def create_purchase_order(
    po_data: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new purchase order"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    # Verify vendor exists and belongs to organization
    vendor_query = select(Vendor).where(
        and_(
            Vendor.id == po_data.vendor_id,
            Vendor.organization_id == current_user.organization_id
        )
    )
    vendor_result = await db.execute(vendor_query)
    vendor = vendor_result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(status_code=400, detail="Vendor not found")

    # Optional validations for project and customer
    if po_data.project_id:
        proj_res = await db.execute(
            select(ProjectModel).where(
                and_(
                    ProjectModel.id == po_data.project_id,
                    ProjectModel.organization_id == current_user.organization_id
                )
            )
        )
        if not proj_res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Project not found")

    if po_data.customer_id:
        cust_res = await db.execute(
            select(CustomerModel).where(
                and_(
                    CustomerModel.id == po_data.customer_id,
                    CustomerModel.organization_id == current_user.organization_id
                )
            )
        )
        if not cust_res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Customer not found")
    
    # Calculate totals from items
    subtotal = sum(item.quantity * item.unit_price for item in po_data.items)
    tax_amount = subtotal * 0.1  # 10% tax (configurable)
    total_amount = subtotal + tax_amount
    
    # Create purchase order
    purchase_order = PurchaseOrder(
        id=str(uuid.uuid4()),
        po_number=generate_po_number(),
        organization_id=current_user.organization_id,
        vendor_id=po_data.vendor_id,
        project_id=po_data.project_id,
        customer_id=po_data.customer_id,
        order_date=po_data.order_date,
        expected_delivery_date=po_data.expected_delivery_date,
        received_date=po_data.received_date,
        priority=po_data.priority,
        department=po_data.department,
        requested_by=po_data.requested_by,
        shipping_address=po_data.shipping_address,
        payment_method=po_data.payment_method,
        notes=po_data.notes,
        terms_and_conditions=po_data.terms_and_conditions,
        internal_reference=po_data.internal_reference,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount
    )
    
    db.add(purchase_order)
    await db.flush()
    
    # Create purchase order items
    for item_data in po_data.items:
        total_price = item_data.quantity * item_data.unit_price

        # Resolve item snapshot fields
        resolved_item_name = item_data.item_name
        resolved_description = item_data.description
        resolved_sku = item_data.sku
        resolved_category = item_data.category
        resolved_unit = item_data.unit or ItemUnit.EACH

        if item_data.item_id:
            # Fetch item and validate organization
            item_result = await db.execute(
                select(ItemModel).where(
                    and_(
                        ItemModel.id == item_data.item_id,
                        ItemModel.organization_id == current_user.organization_id
                    )
                )
            )
            item_obj = item_result.scalar_one_or_none()
            if not item_obj:
                raise HTTPException(status_code=400, detail=f"Item with id {item_data.item_id} not found")
            # Snapshot values from catalog item when not provided
            resolved_item_name = resolved_item_name or item_obj.name
            resolved_description = resolved_description or item_obj.description
            resolved_sku = resolved_sku or item_obj.sku
            resolved_category = resolved_category or item_obj.category
            # Do not attempt to map string unit from item to enum; default handled above

        if not resolved_item_name:
            raise HTTPException(status_code=400, detail="Each purchase order item must have either item_id or item_name")

        po_item = PurchaseOrderItem(
            id=str(uuid.uuid4()),
            purchase_order_id=purchase_order.id,
            item_id=item_data.item_id,
            item_name=resolved_item_name,
            description=resolved_description,
            sku=resolved_sku,
            category=resolved_category,
            quantity=item_data.quantity,
            unit=resolved_unit,
            unit_price=item_data.unit_price,
            total_price=total_price,
            quantity_pending=item_data.quantity,
            notes=item_data.notes
        )
        db.add(po_item)
    
    await db.flush()
    await db.refresh(purchase_order)

    # Commit to persist changes so subsequent requests can see this PO
    await db.commit()
    
    # Load related data
    await db.refresh(purchase_order, ['vendor', 'items'])
    
    # Prepare response
    po_dict = purchase_order.__dict__.copy()
    po_dict['vendor_name'] = purchase_order.vendor.name
    po_dict['items'] = [PurchaseOrderItemResponse.model_validate(item) for item in purchase_order.items]
    
    return PurchaseOrderResponse(**po_dict)


@router.get("/{po_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    po_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific purchase order by ID"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    query = select(PurchaseOrder).options(
        selectinload(PurchaseOrder.vendor),
        selectinload(PurchaseOrder.items)
    ).where(
        and_(
            PurchaseOrder.id == po_id,
            PurchaseOrder.organization_id == current_user.organization_id
        )
    )
    result = await db.execute(query)
    purchase_order = result.scalar_one_or_none()
    
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    # Prepare response
    po_dict = purchase_order.__dict__.copy()
    po_dict['vendor_name'] = purchase_order.vendor.name if purchase_order.vendor else None
    po_dict['items'] = [PurchaseOrderItemResponse.model_validate(item) for item in purchase_order.items]
    
    return PurchaseOrderResponse(**po_dict)


@router.put("/{po_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    po_id: str,
    po_data: PurchaseOrderUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user)
):
    """Update a purchase order"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    # Get existing purchase order
    query = select(PurchaseOrder).options(
        selectinload(PurchaseOrder.vendor),
        selectinload(PurchaseOrder.items)
    ).where(
        and_(
            PurchaseOrder.id == po_id,
            PurchaseOrder.organization_id == current_user.organization_id
        )
    )
    result = await db.execute(query)
    purchase_order = result.scalar_one_or_none()
    
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    # Update purchase order with provided data (excluding items handled separately)
    # Extract items (typed) from payload if provided
    items_payload = po_data.items

    # Update other fields, excluding 'items'
    update_data = po_data.dict(exclude_unset=True, exclude={'items'})
    for field, value in update_data.items():
        setattr(purchase_order, field, value)

    # If items are provided, replace existing items with the provided set
    if items_payload is not None:
        # Delete existing items
        for existing_item in list(purchase_order.items):
            await db.delete(existing_item)
        await db.flush()

        # Add new items
        new_subtotal = 0.0
        for item_data in items_payload:
            line_total = item_data.quantity * item_data.unit_price
            new_subtotal += line_total

            resolved_item_name = item_data.item_name
            resolved_description = item_data.description
            resolved_sku = item_data.sku
            resolved_category = item_data.category
            resolved_unit = item_data.unit or ItemUnit.EACH

            if item_data.item_id:
                item_result = await db.execute(
                    select(ItemModel).where(
                        and_(
                            ItemModel.id == item_data.item_id,
                            ItemModel.organization_id == current_user.organization_id
                        )
                    )
                )
                item_obj = item_result.scalar_one_or_none()
                if not item_obj:
                    raise HTTPException(status_code=400, detail=f"Item with id {item_data.item_id} not found")
                resolved_item_name = resolved_item_name or item_obj.name
                resolved_description = resolved_description or item_obj.description
                resolved_sku = resolved_sku or item_obj.sku
                resolved_category = resolved_category or item_obj.category

            if not resolved_item_name:
                raise HTTPException(status_code=400, detail="Each purchase order item must have either item_id or item_name")

            po_item = PurchaseOrderItem(
                id=str(uuid.uuid4()),
                purchase_order_id=purchase_order.id,
                item_id=item_data.item_id,
                item_name=resolved_item_name,
                description=resolved_description,
                sku=resolved_sku,
                category=resolved_category,
                quantity=item_data.quantity,
                unit=resolved_unit,
                unit_price=item_data.unit_price,
                total_price=line_total,
                quantity_pending=item_data.quantity,
                notes=item_data.notes
            )
            db.add(po_item)

        # Recalculate totals (keeping a simple 10% tax for now as in create)
        tax_amount = new_subtotal * 0.1
        purchase_order.subtotal = new_subtotal
        purchase_order.tax_amount = tax_amount
        purchase_order.total_amount = new_subtotal + tax_amount

    await db.flush()
    await db.refresh(purchase_order)

    # Commit updates so list endpoints reflect changes immediately
    await db.commit()

    await db.refresh(purchase_order, ['vendor', 'items'])
    
    # Prepare response
    po_dict = purchase_order.__dict__.copy()
    po_dict['vendor_name'] = purchase_order.vendor.name if purchase_order.vendor else None
    po_dict['items'] = [PurchaseOrderItemResponse.model_validate(item) for item in purchase_order.items]
    
    return PurchaseOrderResponse(**po_dict)


@router.patch("/{po_id}/status", response_model=PurchaseOrderResponse)
async def update_purchase_order_status(
    po_id: str,
    status_data: PurchaseOrderStatusUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user)
):
    """Update purchase order status"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    # Get existing purchase order
    query = select(PurchaseOrder).options(
        selectinload(PurchaseOrder.vendor),
        selectinload(PurchaseOrder.items)
    ).where(
        and_(
            PurchaseOrder.id == po_id,
            PurchaseOrder.organization_id == current_user.organization_id
        )
    )
    result = await db.execute(query)
    purchase_order = result.scalar_one_or_none()
    
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    # Update status and related fields
    purchase_order.status = status_data.status
    if status_data.approved_by:
        purchase_order.approved_by = status_data.approved_by
    if status_data.received_date:
        purchase_order.received_date = status_data.received_date
    if status_data.notes:
        purchase_order.notes = status_data.notes
    
    await db.flush()
    await db.refresh(purchase_order)

    # Commit status change for visibility across sessions
    await db.commit()
    
    # Prepare response
    po_dict = purchase_order.__dict__.copy()
    po_dict['vendor_name'] = purchase_order.vendor.name if purchase_order.vendor else None
    po_dict['items'] = [PurchaseOrderItemResponse.model_validate(item) for item in purchase_order.items]
    
    return PurchaseOrderResponse(**po_dict)


@router.delete("/{po_id}")
async def delete_purchase_order(
    po_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a purchase order"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    # Check if purchase order exists and belongs to organization
    query = select(PurchaseOrder).where(
        and_(
            PurchaseOrder.id == po_id,
            PurchaseOrder.organization_id == current_user.organization_id
        )
    )
    result = await db.execute(query)
    purchase_order = result.scalar_one_or_none()
    
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    # Delete purchase order (cascade will delete items)
    await db.delete(purchase_order)
    await db.commit()
    
    return {"message": "Purchase order deleted successfully"}


@router.get("/{po_id}/pdf")
async def download_purchase_order_pdf(
    po_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user),
    design: str | None = None,
) -> StreamingResponse:
    """Download purchase order as PDF with organization branding.
    By default, renders the 'Quantity Rental Quotation' layout to match the provided design.
    Pass design=legacy to use the older PO layout.
    """
    # Load purchase order with relationships scoped to user's organization
    query = (
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.vendor),
            selectinload(PurchaseOrder.items),
        )
        .where(
            and_(
                PurchaseOrder.id == po_id,
                PurchaseOrder.organization_id == current_user.organization_id,
            )
        )
    )
    result = await db.execute(query)
    purchase_order = result.scalar_one_or_none()
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    # Fetch organization branding/settings for header
    org_res = await db.execute(select(Organization).where(Organization.id == current_user.organization_id))
    org_obj = org_res.scalar_one_or_none()
    org = {"name": org_obj.name, "settings": org_obj.settings or {}, "branding": org_obj.branding or {}} if org_obj else {}

    # Optionally fetch project for header context
    project_name = None
    if purchase_order.project_id:
        proj_res = await db.execute(select(ProjectModel).where(ProjectModel.id == purchase_order.project_id))
        proj = proj_res.scalar_one_or_none()
        if proj:
            project_name = getattr(proj, 'name', None)

    # Build payload for PDF service
    po_data = {
        "po_number": purchase_order.po_number,
        "status": purchase_order.status.value if getattr(purchase_order, "status", None) else "draft",
        "vendor_name": purchase_order.vendor.name if purchase_order.vendor else None,
        "order_date": purchase_order.order_date.isoformat() if purchase_order.order_date else None,
        "expected_delivery_date": purchase_order.expected_delivery_date.isoformat() if purchase_order.expected_delivery_date else None,
        "received_date": purchase_order.received_date.isoformat() if purchase_order.received_date else None,
        "subtotal": float(purchase_order.subtotal or 0),
        "tax_amount": float(purchase_order.tax_amount or 0),
        "total_amount": float(purchase_order.total_amount or 0),
        "terms_and_conditions": purchase_order.terms_and_conditions,
        # Fields used by quotation layout
        "quotation_number": purchase_order.po_number,
        "quotation_date": purchase_order.order_date.isoformat() if purchase_order.order_date else None,
        "rental_period": (purchase_order.notes or '').strip() or '4-week',
        "project_name": project_name,
        # You can extend with plot_number / structural_element etc. via custom fields later
        "items": [
            {
                "item_name": it.item_name,
                "description": it.description,
                "quantity": float(it.quantity or 0),
                "unit": it.unit.value if hasattr(it.unit, "value") else (it.unit or "each"),
                "unit_price": float(it.unit_price or 0),
                "total_price": float(it.total_price or 0),
                # Optional guarantee rate; default to 0 if not stored
                "guarantee_rate": 0,
            }
            for it in purchase_order.items
        ],
    }

    pdf_service = PDFService()
    if design == 'legacy':
        pdf_buffer = pdf_service.generate_purchase_order_pdf(po_data, org=org)
    else:
        pdf_buffer = pdf_service.generate_quantity_rental_quotation_pdf(po_data, org=org)

    return StreamingResponse(
        io.BytesIO(pdf_buffer.read()),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=purchase_order_{purchase_order.po_number}.pdf"},
    )


@router.get("/stats/overview", response_model=PurchaseOrderStats)
async def get_purchase_order_stats(
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user)
):
    """Get purchase order statistics for the current organization"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    # Get total count and status distribution
    total_query = select(func.count(PurchaseOrder.id)).where(
        PurchaseOrder.organization_id == current_user.organization_id
    )
    total_result = await db.execute(total_query)
    total_orders = total_result.scalar()
    
    # Status counts
    status_query = select(PurchaseOrder.status, func.count(PurchaseOrder.id)).where(
        PurchaseOrder.organization_id == current_user.organization_id
    ).group_by(PurchaseOrder.status)
    status_result = await db.execute(status_query)
    by_status = {row[0]: row[1] for row in status_result.fetchall()}
    
    # Priority distribution
    priority_query = select(PurchaseOrder.priority, func.count(PurchaseOrder.id)).where(
        PurchaseOrder.organization_id == current_user.organization_id
    ).group_by(PurchaseOrder.priority)
    priority_result = await db.execute(priority_query)
    by_priority = {row[0]: row[1] for row in priority_result.fetchall()}
    
    # Department distribution
    dept_query = select(PurchaseOrder.department, func.count(PurchaseOrder.id)).where(
        and_(
            PurchaseOrder.organization_id == current_user.organization_id,
            PurchaseOrder.department.isnot(None)
        )
    ).group_by(PurchaseOrder.department)
    dept_result = await db.execute(dept_query)
    by_department = {row[0]: row[1] for row in dept_result.fetchall()}
    
    # Financial stats
    total_spent_query = select(func.sum(PurchaseOrder.total_amount)).where(
        and_(
            PurchaseOrder.organization_id == current_user.organization_id,
            PurchaseOrder.status.in_(['approved', 'ordered', 'received'])
        )
    )
    total_spent_result = await db.execute(total_spent_query)
    total_spent = total_spent_result.scalar() or 0.0
    
    avg_order_query = select(func.avg(PurchaseOrder.total_amount)).where(
        PurchaseOrder.organization_id == current_user.organization_id
    )
    avg_order_result = await db.execute(avg_order_query)
    average_order_value = avg_order_result.scalar() or 0.0
    
    # Monthly trends (simplified - last 12 months)
    monthly_trends = {}  # This would need more complex date queries
    
    return PurchaseOrderStats(
        total_orders=total_orders,
        pending_orders=by_status.get('pending', 0),
        approved_orders=by_status.get('approved', 0),
        received_orders=by_status.get('received', 0),
        cancelled_orders=by_status.get('cancelled', 0),
        total_spent=total_spent,
        average_order_value=round(average_order_value, 2),
        by_status=by_status,
        by_priority=by_priority,
        by_department=by_department,
        monthly_trends=monthly_trends
    )