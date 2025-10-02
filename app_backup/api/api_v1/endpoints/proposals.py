from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
import uuid
from datetime import datetime, timedelta

from ....db.database import get_db
from ....models.proposal import Proposal as ProposalModel, ProposalStatus, ProposalType
from ....models.user import User
from ....models.customer import Customer
from ....schemas.proposal import (
    Proposal, ProposalCreate, ProposalUpdate, ProposalList, ProposalStats
)
from ...deps import get_current_active_user, require_manager

router = APIRouter()


@router.get("/", response_model=ProposalList)
async def get_proposals(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
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
    proposals = result.scalars().all()
    
    return ProposalList(
        items=proposals,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.get("/stats", response_model=ProposalStats)
async def get_proposal_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
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
    
    return proposal


@router.post("/", response_model=Proposal, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    proposal_data: ProposalCreate,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new proposal"""
    
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
    db: AsyncSession = Depends(get_db),
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
            proposal.sent_date = datetime.utcnow()
        elif proposal_data.status == ProposalStatus.VIEWED and not proposal.viewed_date:
            proposal.viewed_date = datetime.utcnow()
        elif proposal_data.status in [ProposalStatus.ACCEPTED, ProposalStatus.REJECTED] and not proposal.responded_date:
            proposal.responded_date = datetime.utcnow()
    
    await db.commit()
    await db.refresh(proposal)
    
    # Load relationships for response
    await db.refresh(proposal, ['customer', 'created_by'])
    
    return proposal


@router.delete("/{proposal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proposal(
    proposal_id: str,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
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
    if proposal.status != ProposalStatus.DRAFT and current_user.role != "admin":
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
    db: AsyncSession = Depends(get_db),
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
    proposal.sent_date = datetime.utcnow()
    
    # Set valid_until if not set (default to 30 days)
    if not proposal.valid_until:
        proposal.valid_until = datetime.utcnow() + timedelta(days=30)
    
    await db.commit()
    
    # TODO: Add background task to send email to customer
    # background_tasks.add_task(send_proposal_email, proposal.id, proposal.customer.email)
    
    return {"message": "Proposal sent successfully"}


@router.post("/{proposal_id}/accept")
async def accept_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
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
    
    # Update proposal status
    proposal.status = ProposalStatus.ACCEPTED
    proposal.responded_date = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Proposal accepted successfully"}


@router.post("/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    rejection_reason: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
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
    
    # Update proposal status
    proposal.status = ProposalStatus.REJECTED
    proposal.responded_date = datetime.utcnow()
    if rejection_reason:
        proposal.rejection_reason = rejection_reason
    
    await db.commit()
    
    return {"message": "Proposal rejected successfully"}
