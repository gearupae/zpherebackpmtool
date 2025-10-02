from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
import uuid
import io
from datetime import datetime, timedelta, timezone

from ....db.database import get_db
from ...deps_tenant import get_tenant_db
from ....models.proposal import Proposal as ProposalModel, ProposalStatus, ProposalType
from ....models.user import User
from ....models.customer import Customer
from ....models.notification import (
    Notification as NotificationModel,
    NotificationType,
    NotificationPriority,
)
from ....schemas.proposal import (
    Proposal, ProposalCreate, ProposalUpdate, ProposalList, ProposalStats
)
from ...deps import get_current_active_user, require_manager
from ....services.pdf_service import PDFService
from ....models.organization import Organization
from .websockets import send_notification as ws_send_notification

router = APIRouter()


def _serialize_proposal(p: ProposalModel) -> dict:
    """Safe serializer to plain dict for Proposal to avoid response validation issues."""
    def enum_val(e):
        try:
            return e.value if hasattr(e, 'value') else str(e)
        except Exception:
            return str(e) if e is not None else None

    return {
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "proposal_number": p.proposal_number,
        "organization_id": p.organization_id,
        "customer_id": p.customer_id,
        "created_by_id": p.created_by_id,
        "proposal_type": enum_val(p.proposal_type),
        "status": enum_val(p.status) if p.status else enum_val(ProposalStatus.DRAFT),
        "content": p.content or {},
        "template_id": p.template_id,
        "custom_template": p.custom_template or {},
        "total_amount": p.total_amount,
        "currency": p.currency or "usd",
        "valid_until": p.valid_until,
        "sent_date": p.sent_date,
        "viewed_date": p.viewed_date,
        "responded_date": p.responded_date,
        "response_notes": p.response_notes,
        "rejection_reason": p.rejection_reason,
        "follow_up_date": p.follow_up_date,
        "notes": p.notes,
        "tags": p.tags or [],
        "custom_fields": p.custom_fields or {},
        "is_template": bool(p.is_template),
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        # Computed
        "is_expired": bool(getattr(p, "is_expired", False)),
        "status_color": getattr(p, "status_color", "gray"),
    }


async def _create_notification(
    db: AsyncSession,
    *,
    user_id: str,
    organization_id: str,
    title: str,
    message: str,
    notification_type: NotificationType = NotificationType.SYSTEM_ALERT,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    category: str = "proposal",
    context_data: Optional[dict] = None,
) -> None:
    """Create an in-app notification record for a user in the current tenant DB.
    Commits are handled by the caller; this only adds the row to the session.
    """
    notification = NotificationModel(
        title=title,
        message=message,
        short_description=title,
        notification_type=notification_type,
        priority=priority,
        category=category,
        user_id=user_id,
        organization_id=organization_id,
        relevance_score=0.7,
        context_data=context_data or {},
        action_required=False,
        auto_generated=True,
        delivery_channels=["in_app"],
        source="proposals",
        tags=["proposal"],
    )
    db.add(notification)


@router.get("/", response_model=ProposalList)
async def get_proposals(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[ProposalStatus] = None,
    proposal_type: Optional[ProposalType] = None,
    customer_id: Optional[str] = None,
) -> Any:
    """Get proposals with pagination and filtering"""
    
    # Build base query
    query = select(ProposalModel).where(
        ProposalModel.organization_id == current_user.organization_id
    )
    
    # Apply filters
    if search:
        search_filter = or_(
            ProposalModel.title.ilike(f"%{search}%"),
            ProposalModel.proposal_number.ilike(f"%{search}%"),
            ProposalModel.description.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    if status:
        query = query.where(ProposalModel.status == status)
    
    if proposal_type:
        query = query.where(ProposalModel.proposal_type == proposal_type)
    
    if customer_id:
        query = query.where(ProposalModel.customer_id == customer_id)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and get results
    query = query.order_by(ProposalModel.created_at.desc())
    query = query.offset((page - 1) * size).limit(size)
    
    # Load relationships
    query = query.options(
        selectinload(ProposalModel.customer),
        selectinload(ProposalModel.created_by)
    )
    
    result = await db.execute(query)
    proposals = result.scalars().unique().all()

    serialized = [_serialize_proposal(p) for p in proposals]
    return ProposalList(
        items=[Proposal.model_validate(sp) for sp in serialized],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.get("/stats", response_model=ProposalStats)
async def get_proposal_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get proposal statistics"""
    
    base_query = select(ProposalModel).where(
        ProposalModel.organization_id == current_user.organization_id
    )
    
    # Total proposals
    total_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total_proposals = total_result.scalar()
    
    # Count by status
    status_counts = {}
    for status in ProposalStatus:
        count_result = await db.execute(
            select(func.count()).select_from(
                base_query.where(ProposalModel.status == status).subquery()
            )
        )
        status_counts[status.value] = count_result.scalar()
    
    # Total value
    value_result = await db.execute(
        select(func.coalesce(func.sum(ProposalModel.total_amount), 0)).select_from(
            base_query.subquery()
        )
    )
    total_value = value_result.scalar()
    
    # Conversion rate (accepted / sent)
    sent_count = status_counts.get('sent', 0) + status_counts.get('viewed', 0) + status_counts.get('accepted', 0) + status_counts.get('rejected', 0)
    accepted_count = status_counts.get('accepted', 0)
    conversion_rate = (accepted_count / sent_count * 100) if sent_count > 0 else 0
    
    return ProposalStats(
        total_proposals=total_proposals,
        draft_proposals=status_counts.get('draft', 0),
        sent_proposals=status_counts.get('sent', 0),
        viewed_proposals=status_counts.get('viewed', 0),
        accepted_proposals=status_counts.get('accepted', 0),
        rejected_proposals=status_counts.get('rejected', 0),
        expired_proposals=status_counts.get('expired', 0),
        total_value=total_value,
        conversion_rate=conversion_rate
    )


@router.get("/{proposal_id}", response_model=Proposal)
async def get_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific proposal by ID"""
    
    query = select(ProposalModel).where(
        and_(
            ProposalModel.id == proposal_id,
            ProposalModel.organization_id == current_user.organization_id
        )
    ).options(
        selectinload(ProposalModel.customer),
        selectinload(ProposalModel.created_by)
    )
    
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()
    
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found"
        )
    
    return Proposal.model_validate(_serialize_proposal(proposal))


@router.post("/", response_model=Proposal, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    proposal_data: ProposalCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new proposal (any active user)"""
    
    # Verify customer exists and belongs to organization
    customer_query = select(Customer).where(
        and_(
            Customer.id == proposal_data.customer_id,
            Customer.organization_id == current_user.organization_id
        )
    )
    customer_result = await db.execute(customer_query)
    customer = customer_result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Generate proposal number
    proposal_number = f"PROP-{datetime.now().strftime('%Y-%m')}-{str(uuid.uuid4())[:8].upper()}"
    
    # Create proposal
    proposal = ProposalModel(
        id=str(uuid.uuid4()),
        proposal_number=proposal_number,
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
        **proposal_data.dict()
    )
    
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)
    
    # Load relationships for response
    await db.refresh(proposal, ['customer', 'created_by'])
    
    return proposal


@router.put("/{proposal_id}", response_model=Proposal)
async def update_proposal(
    proposal_id: str,
    proposal_data: ProposalUpdate,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a proposal"""
    
    # Get existing proposal
    query = select(ProposalModel).where(
        and_(
            ProposalModel.id == proposal_id,
            ProposalModel.organization_id == current_user.organization_id
        )
    )
    
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()
    
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found"
        )
    
    # If customer_id is being updated, verify it exists
    if proposal_data.customer_id and proposal_data.customer_id != proposal.customer_id:
        customer_query = select(Customer).where(
            and_(
                Customer.id == proposal_data.customer_id,
                Customer.organization_id == current_user.organization_id
            )
        )
        customer_result = await db.execute(customer_query)
        customer = customer_result.scalar_one_or_none()
        
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
    
    # Update proposal
    update_data = proposal_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(proposal, field, value)
    
    # Update timestamps based on status changes
    if proposal_data.status:
        if proposal_data.status == ProposalStatus.SENT and not proposal.sent_date:
            proposal.sent_date = datetime.now(timezone.utc)
        elif proposal_data.status == ProposalStatus.VIEWED and not proposal.viewed_date:
            proposal.viewed_date = datetime.now(timezone.utc)
        elif proposal_data.status in [ProposalStatus.ACCEPTED, ProposalStatus.REJECTED] and not proposal.responded_date:
            proposal.responded_date = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(proposal)
    
    # Load relationships for response
    await db.refresh(proposal, ['customer', 'created_by'])
    
    return proposal


@router.delete("/{proposal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proposal(
    proposal_id: str,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a proposal"""
    
    query = select(ProposalModel).where(
        and_(
            ProposalModel.id == proposal_id,
            ProposalModel.organization_id == current_user.organization_id
        )
    )
    
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()
    
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found"
        )
    
    # Only allow deletion of draft proposals or by admin
    # Allow deletion if draft, or if the user is a platform admin
    if proposal.status != ProposalStatus.DRAFT and not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only delete draft proposals"
        )
    
    await db.delete(proposal)
    await db.commit()
    return


@router.post("/{proposal_id}/send")
async def send_proposal(
    proposal_id: str,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Any:
    """Send a proposal to customer"""
    
    query = select(ProposalModel).where(
        and_(
            ProposalModel.id == proposal_id,
            ProposalModel.organization_id == current_user.organization_id
        )
    ).options(
        selectinload(ProposalModel.customer)
    )
    
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()
    
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found"
        )
    
    if proposal.status != ProposalStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only send draft proposals"
        )
    
    # Update proposal status
    proposal.status = ProposalStatus.SENT
    proposal.sent_date = datetime.now(timezone.utc)
    
    # Set valid_until if not set (default to 30 days)
    if not proposal.valid_until:
        proposal.valid_until = datetime.now(timezone.utc) + timedelta(days=30)

    # Add in-app notifications (notify creator; if different, also notify actor)
    context = {
        "proposal_id": str(proposal.id),
        "proposal_number": proposal.proposal_number,
        "customer_id": proposal.customer_id,
        "status": "sent",
    }
    await _create_notification(
        db,
        user_id=proposal.created_by_id,
        organization_id=current_user.organization_id,
        title=f"Proposal sent: {proposal.proposal_number}",
        message=f"'{proposal.title}' has been sent to the customer.",
        notification_type=NotificationType.SYSTEM_ALERT,
        priority=NotificationPriority.NORMAL,
        context_data=context,
    )
    if proposal.created_by_id != current_user.id:
        await _create_notification(
            db,
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            title=f"Proposal sent: {proposal.proposal_number}",
            message=f"You sent proposal '{proposal.title}' to the customer.",
            notification_type=NotificationType.SYSTEM_ALERT,
            priority=NotificationPriority.NORMAL,
            context_data=context,
        )
    
    await db.commit()

    # Real-time WS notifications
    ws_payload = {
        "id": str(uuid.uuid4()),
        "title": f"Proposal sent: {proposal.proposal_number}",
        "message": f"'{proposal.title}' has been sent to the customer.",
        "notification_type": "system_alert",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "context": context,
    }
    # Notify creator
    await ws_send_notification(proposal.created_by_id, current_user.organization_id, ws_payload)
    # Notify actor if different
    if proposal.created_by_id != current_user.id:
        await ws_send_notification(current_user.id, current_user.organization_id, ws_payload)
    
    # TODO: Add background task to send email to customer
    # background_tasks.add_task(send_proposal_email, proposal.id, proposal.customer.email)
    
    return {"message": "Proposal sent successfully"}


@router.post("/{proposal_id}/accept")
async def accept_proposal(
    proposal_id: str,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Accept a proposal (typically called by customer or admin)"""
    
    query = select(ProposalModel).where(
        and_(
            ProposalModel.id == proposal_id,
            ProposalModel.organization_id == current_user.organization_id
        )
    )
    
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()
    
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found"
        )
    
    if proposal.status not in [ProposalStatus.SENT, ProposalStatus.VIEWED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only accept sent or viewed proposals"
        )

    # Expiry guard
    if proposal.valid_until and proposal.valid_until < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proposal has expired and cannot be accepted. Please resend or extend validity."
        )
    
    # Update proposal status
    proposal.status = ProposalStatus.ACCEPTED
    proposal.responded_date = datetime.now(timezone.utc)

    # Add in-app notifications
    context = {
        "proposal_id": str(proposal.id),
        "proposal_number": proposal.proposal_number,
        "customer_id": proposal.customer_id,
        "status": "accepted",
    }
    await _create_notification(
        db,
        user_id=proposal.created_by_id,
        organization_id=current_user.organization_id,
        title=f"Proposal accepted: {proposal.proposal_number}",
        message=f"'{proposal.title}' was accepted.",
        notification_type=NotificationType.SYSTEM_ALERT,
        priority=NotificationPriority.HIGH,
        context_data=context,
    )
    if proposal.created_by_id != current_user.id:
        await _create_notification(
            db,
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            title=f"Proposal accepted: {proposal.proposal_number}",
            message=f"You marked proposal '{proposal.title}' as accepted.",
            notification_type=NotificationType.SYSTEM_ALERT,
            priority=NotificationPriority.NORMAL,
            context_data=context,
        )
    
    await db.commit()

    # Real-time WS notifications
    ws_payload = {
        "id": str(uuid.uuid4()),
        "title": f"Proposal accepted: {proposal.proposal_number}",
        "message": f"'{proposal.title}' was accepted.",
        "notification_type": "system_alert",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "context": context,
    }
    await ws_send_notification(proposal.created_by_id, current_user.organization_id, ws_payload)
    if proposal.created_by_id != current_user.id:
        await ws_send_notification(current_user.id, current_user.organization_id, ws_payload)
    
    return {"message": "Proposal accepted successfully"}


@router.post("/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    rejection_reason: Optional[str] = None,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Reject a proposal (typically called by customer or admin)"""
    
    query = select(ProposalModel).where(
        and_(
            ProposalModel.id == proposal_id,
            ProposalModel.organization_id == current_user.organization_id
        )
    )
    
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()
    
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found"
        )
    
    if proposal.status not in [ProposalStatus.SENT, ProposalStatus.VIEWED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only reject sent or viewed proposals"
        )

    # Expiry guard
    if proposal.valid_until and proposal.valid_until < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proposal has expired and cannot be rejected. Please resend or extend validity."
        )
    
    # Update proposal status
    proposal.status = ProposalStatus.REJECTED
    proposal.responded_date = datetime.now(timezone.utc)
    if rejection_reason:
        proposal.rejection_reason = rejection_reason

    # Add in-app notifications
    context = {
        "proposal_id": str(proposal.id),
        "proposal_number": proposal.proposal_number,
        "customer_id": proposal.customer_id,
        "status": "rejected",
        "rejection_reason": rejection_reason,
    }
    await _create_notification(
        db,
        user_id=proposal.created_by_id,
        organization_id=current_user.organization_id,
        title=f"Proposal rejected: {proposal.proposal_number}",
        message=f"'{proposal.title}' was rejected." + (f" Reason: {rejection_reason}" if rejection_reason else ""),
        notification_type=NotificationType.SYSTEM_ALERT,
        priority=NotificationPriority.HIGH,
        context_data=context,
    )
    if proposal.created_by_id != current_user.id:
        await _create_notification(
            db,
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            title=f"Proposal rejected: {proposal.proposal_number}",
            message=f"You marked proposal '{proposal.title}' as rejected.",
            notification_type=NotificationType.SYSTEM_ALERT,
            priority=NotificationPriority.NORMAL,
            context_data=context,
        )
    
    await db.commit()

    # Real-time WS notifications
    ws_payload = {
        "id": str(uuid.uuid4()),
        "title": f"Proposal rejected: {proposal.proposal_number}",
        "message": f"'{proposal.title}' was rejected." + (f" Reason: {rejection_reason}" if rejection_reason else ""),
        "notification_type": "system_alert",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "context": context,
    }
    await ws_send_notification(proposal.created_by_id, current_user.organization_id, ws_payload)
    if proposal.created_by_id != current_user.id:
        await ws_send_notification(current_user.id, current_user.organization_id, ws_payload)
    
    return {"message": "Proposal rejected successfully"}


@router.get("/{proposal_id}/pdf")
async def download_proposal_pdf(
    proposal_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> StreamingResponse:
    """Download proposal as PDF from the current tenant database"""
    # Get proposal with relationships, scoped to the user's organization
    result = await db.execute(
        select(ProposalModel)
        .options(selectinload(ProposalModel.customer))
        .where(
            and_(
                ProposalModel.id == proposal_id,
                ProposalModel.organization_id == current_user.organization_id,
            )
        )
    )
    proposal = result.scalar_one_or_none()
    
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found"
        )
    
    # Convert to dict for PDF service
    proposal_data = {
        "id": str(proposal.id),
        "proposal_number": proposal.proposal_number,
        "title": proposal.title,
        "description": proposal.description,
        "status": proposal.status.value if proposal.status else "draft",
        "total_amount": proposal.total_amount,
        "currency": proposal.currency,
        "valid_until": proposal.valid_until.isoformat() if proposal.valid_until else None,
        "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
        "customer": {
            "display_name": f"{proposal.customer.first_name} {proposal.customer.last_name}" if proposal.customer else "Unknown Client",
            "company_name": proposal.customer.company_name if proposal.customer else None,
            "email": proposal.customer.email if proposal.customer else None,
        } if proposal.customer else {},
        "content": proposal.content or {"items": []},
        "custom_fields": proposal.custom_fields or {},
    }
    
    # Generate PDF
    pdf_service = PDFService()
    # Organization branding for header
    org_res = await db.execute(select(Organization).where(Organization.id == current_user.organization_id))
    org_obj = org_res.scalar_one_or_none()
    org = {"name": org_obj.name, "settings": org_obj.settings or {}, "branding": org_obj.branding or {}} if org_obj else {}
    pdf_buffer = pdf_service.generate_proposal_pdf(proposal_data, org=org)
    
    # Return as streaming response
    return StreamingResponse(
        io.BytesIO(pdf_buffer.read()),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=proposal_{proposal.proposal_number}.pdf"}
    )
