from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from ....api.deps_tenant import get_tenant_db as get_db
from ....models.user import User
from ....models.organization import Organization
from ....models.decision_log import DecisionLog, DecisionStatus
from ....models.project import Project
from ....schemas.decision_log import (
    DecisionLogCreate,
    DecisionLogUpdate,
    DecisionLog as DecisionLogSchema,
    DecisionLogResponse
)
from ...deps_tenant import get_current_active_user_master as get_current_active_user, get_current_organization_master as get_current_organization

router = APIRouter()


@router.post("/", response_model=DecisionLogResponse, status_code=status.HTTP_201_CREATED)
async def create_decision_log(
    decision_data: DecisionLogCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new decision log entry"""
    # Verify project belongs to organization
    project_result = await db.execute(
        select(Project).where(
            and_(
                Project.id == decision_data.project_id,
                Project.organization_id == current_org.id
            )
        )
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Create decision log
    decision_log = DecisionLog(
        **decision_data.model_dump(),
        decision_maker_id=current_user.id
    )
    
    db.add(decision_log)
    await db.commit()
    await db.refresh(decision_log)
    
    return await _enrich_decision_response(decision_log, db)


@router.get("/", response_model=List[DecisionLogResponse])
async def get_decision_logs(
    project_id: str = None,
    category: str = None,
    status: DecisionStatus = None,
    impact_level: str = None,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get decision logs with filtering"""
    query = select(DecisionLog).options(
        selectinload(DecisionLog.project),
        selectinload(DecisionLog.decision_maker)
    )
    
    conditions = []
    
    if project_id:
        # Verify project belongs to organization
        project_result = await db.execute(
            select(Project).where(
                and_(
                    Project.id == project_id,
                    Project.organization_id == current_org.id
                )
            )
        )
        if not project_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        conditions.append(DecisionLog.project_id == project_id)
    else:
        # Filter by organization's projects
        org_projects_subquery = select(Project.id).where(
            Project.organization_id == current_org.id
        )
        conditions.append(DecisionLog.project_id.in_(org_projects_subquery))
    
    if category:
        conditions.append(DecisionLog.category == category)
        
    if status:
        conditions.append(DecisionLog.status == status)
        
    if impact_level:
        conditions.append(DecisionLog.impact_level == impact_level)
    
    query = query.where(and_(*conditions)).order_by(DecisionLog.decision_number.desc())
    
    result = await db.execute(query)
    decision_logs = result.scalars().all()
    
    return [await _enrich_decision_response(decision, db) for decision in decision_logs]


@router.get("/{decision_id}", response_model=DecisionLogResponse)
async def get_decision_log(
    decision_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get a specific decision log"""
    decision_log = await _get_decision_or_404(decision_id, current_org.id, db)
    return await _enrich_decision_response(decision_log, db)


@router.put("/{decision_id}", response_model=DecisionLogResponse)
async def update_decision_log(
    decision_id: str,
    decision_update: DecisionLogUpdate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update a decision log"""
    decision_log = await _get_decision_or_404(decision_id, current_org.id, db)
    
    # Update decision log
    for field, value in decision_update.model_dump(exclude_unset=True).items():
        setattr(decision_log, field, value)
    
    await db.commit()
    await db.refresh(decision_log)
    
    return await _enrich_decision_response(decision_log, db)


@router.post("/{decision_id}/implement", response_model=DecisionLogResponse)
async def implement_decision(
    decision_id: str,
    implementation_notes: str = None,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Mark decision as implemented"""
    decision_log = await _get_decision_or_404(decision_id, current_org.id, db)
    
    decision_log.status = DecisionStatus.IMPLEMENTED
    decision_log.implementation_date = func.now()
    if implementation_notes:
        decision_log.implementation_notes = implementation_notes
    
    await db.commit()
    await db.refresh(decision_log)
    
    return await _enrich_decision_response(decision_log, db)


@router.post("/{decision_id}/approve", response_model=DecisionLogResponse)
async def approve_decision(
    decision_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Approve a decision"""
    decision_log = await _get_decision_or_404(decision_id, current_org.id, db)
    
    decision_log.status = DecisionStatus.APPROVED
    
    # Add current user to approvers list if not already there
    approvers = decision_log.approvers or []
    if current_user.id not in approvers:
        approvers.append(current_user.id)
        decision_log.approvers = approvers
    
    await db.commit()
    await db.refresh(decision_log)
    
    return await _enrich_decision_response(decision_log, db)


@router.post("/{decision_id}/reject", response_model=DecisionLogResponse)
async def reject_decision(
    decision_id: str,
    rejection_reason: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Reject a decision"""
    decision_log = await _get_decision_or_404(decision_id, current_org.id, db)
    
    decision_log.status = DecisionStatus.REJECTED
    
    # Add rejection reason to important notes
    important_notes = decision_log.assumptions or []
    important_notes.append(f"Rejected by {current_user.first_name} {current_user.last_name}: {rejection_reason}")
    decision_log.assumptions = important_notes
    
    await db.commit()
    await db.refresh(decision_log)
    
    return await _enrich_decision_response(decision_log, db)


@router.delete("/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_decision_log(
    decision_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a decision log entry"""
    decision_log = await _get_decision_or_404(decision_id, current_org.id, db)
    await db.delete(decision_log)
    await db.commit()
    return None


@router.get("/stats/by-category", response_model=List[dict])
async def get_decision_stats_by_category(
    project_id: str = None,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get decision statistics by category"""
    query = select(
        DecisionLog.category,
        func.count(DecisionLog.id).label('count'),
        DecisionLog.status
    ).join(Project)
    
    conditions = [Project.organization_id == current_org.id]
    
    if project_id:
        conditions.append(DecisionLog.project_id == project_id)
    
    query = query.where(and_(*conditions)).group_by(DecisionLog.category, DecisionLog.status)
    
    result = await db.execute(query)
    stats = result.all()
    
    # Format stats
    category_stats = {}
    for category, count, status in stats:
        if category not in category_stats:
            category_stats[category] = {"category": category, "total": 0, "by_status": {}}
        category_stats[category]["total"] += count
        category_stats[category]["by_status"][status] = count
    
    return list(category_stats.values())


async def _get_decision_or_404(
    decision_id: str, 
    organization_id: str, 
    db: AsyncSession
) -> DecisionLog:
    """Get decision log or raise 404"""
    result = await db.execute(
        select(DecisionLog)
        .options(
            selectinload(DecisionLog.project),
            selectinload(DecisionLog.decision_maker)
        )
        .join(Project)
        .where(
            and_(
                DecisionLog.id == decision_id,
                Project.organization_id == organization_id
            )
        )
    )
    decision_log = result.scalar_one_or_none()
    if not decision_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision log not found"
        )
    return decision_log


async def _enrich_decision_response(
    decision_log: DecisionLog, 
    db: AsyncSession
) -> DecisionLogResponse:
    """Enrich decision log with additional data"""
    response_data = {
        **decision_log.__dict__,
        "decision_maker_name": None,
        "project_name": None,
        "stakeholder_names": [],
        "approver_names": [],
    }
    
    if decision_log.decision_maker:
        response_data["decision_maker_name"] = f"{decision_log.decision_maker.first_name} {decision_log.decision_maker.last_name}"
    
    if decision_log.project:
        response_data["project_name"] = decision_log.project.name
    
    # Get stakeholder and approver names
    if decision_log.stakeholders:
        stakeholder_result = await db.execute(
            select(User).where(User.id.in_(decision_log.stakeholders))
        )
        stakeholders = stakeholder_result.scalars().all()
        response_data["stakeholder_names"] = [f"{u.first_name} {u.last_name}" for u in stakeholders]
    
    if decision_log.approvers:
        approver_result = await db.execute(
            select(User).where(User.id.in_(decision_log.approvers))
        )
        approvers = approver_result.scalars().all()
        response_data["approver_names"] = [f"{u.first_name} {u.last_name}" for u in approvers]
    
    return DecisionLogResponse(**response_data)





