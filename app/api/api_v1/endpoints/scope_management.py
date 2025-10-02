"""Scope and Change Management API endpoints"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from ....api.deps_tenant import get_current_active_user_master as get_current_active_user, get_tenant_db
from ....models.user import User
from ....models.scope_management import (
    ProjectScope, ChangeRequest, ScopeTimeline, ScopeBaseline
)
from ....schemas.scope_management import (
    ProjectScope as ProjectScopeSchema, ProjectScopeCreate, ProjectScopeUpdate,
    ChangeRequest as ChangeRequestSchema, ChangeRequestCreate, ChangeRequestUpdate,
    ScopeTimeline as ScopeTimelineSchema, ScopeTimelineCreate,
    ScopeBaseline as ScopeBaselineSchema, ScopeBaselineCreate, ScopeBaselineUpdate,
    ScopeAnalysis, ChangeRequestSummary, ScopeVisualData, ImpactAssessment
)

router = APIRouter()


# Project Scope Endpoints
@router.get("/projects/{project_id}/scope", response_model=List[ProjectScopeSchema])
async def get_project_scope(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    is_active: Optional[bool] = Query(None),
    scope_type: Optional[str] = Query(None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Get project scope items"""
    stmt = select(ProjectScope).where(
        ProjectScope.project_id == project_id
    )
    
    if is_active is not None:
        stmt = stmt.where(ProjectScope.is_active == is_active)
    
    if scope_type:
        stmt = stmt.where(ProjectScope.scope_type == scope_type)
    
    stmt = stmt.order_by(ProjectScope.created_at.desc())
    stmt = stmt.offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    scope_items = result.scalars().all()
    
    return scope_items


@router.post("/projects/{project_id}/scope", response_model=ProjectScopeSchema)
async def create_project_scope(
    project_id: str,
    scope_data: ProjectScopeCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new project scope item"""
    if scope_data.project_id != project_id:
        raise HTTPException(status_code=400, detail="Project ID mismatch")
    
    scope_item = ProjectScope(
        created_by_id=current_user.id,
        **scope_data.dict()
    )
    
    db.add(scope_item)
    await db.commit()
    await db.refresh(scope_item)
    
    # Create timeline entry
    timeline_entry = ScopeTimeline(
        project_id=project_id,
        event_type="scope_added",
        event_description=f"Added scope item: {scope_item.name}",
        related_scope_id=scope_item.id,
        created_by_id=current_user.id,
        impact_summary={"type": "addition", "effort_estimate": scope_item.current_effort_estimate}
    )
    db.add(timeline_entry)
    await db.commit()
    
    return scope_item


@router.get("/scope/{scope_id}", response_model=ProjectScopeSchema)
async def get_scope_item(
    scope_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific scope item"""
    stmt = select(ProjectScope).where(ProjectScope.id == scope_id)
    result = await db.execute(stmt)
    scope_item = result.scalar_one_or_none()
    
    if not scope_item:
        raise HTTPException(status_code=404, detail="Scope item not found")
    
    return scope_item


@router.put("/scope/{scope_id}", response_model=ProjectScopeSchema)
async def update_scope_item(
    scope_id: str,
    scope_data: ProjectScopeUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a scope item"""
    stmt = select(ProjectScope).where(ProjectScope.id == scope_id)
    result = await db.execute(stmt)
    scope_item = result.scalar_one_or_none()
    
    if not scope_item:
        raise HTTPException(status_code=404, detail="Scope item not found")
    
    # Track changes for timeline
    changes = []
    for field, value in scope_data.dict(exclude_unset=True).items():
        if hasattr(scope_item, field) and getattr(scope_item, field) != value:
            changes.append(f"{field}: {getattr(scope_item, field)} → {value}")
            setattr(scope_item, field, value)
    
    scope_item.last_modified_by_id = current_user.id
    
    await db.commit()
    await db.refresh(scope_item)
    
    # Create timeline entry if there were changes
    if changes:
        timeline_entry = ScopeTimeline(
            project_id=scope_item.project_id,
            event_type="scope_modified",
            event_description=f"Modified scope item: {scope_item.name}",
            related_scope_id=scope_item.id,
            created_by_id=current_user.id,
            impact_summary={"changes": changes}
        )
        db.add(timeline_entry)
        await db.commit()
    
    return scope_item


@router.delete("/scope/{scope_id}")
async def delete_scope_item(
    scope_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Delete (deactivate) a scope item"""
    stmt = select(ProjectScope).where(ProjectScope.id == scope_id)
    result = await db.execute(stmt)
    scope_item = result.scalar_one_or_none()
    
    if not scope_item:
        raise HTTPException(status_code=404, detail="Scope item not found")
    
    scope_item.is_active = False
    scope_item.last_modified_by_id = current_user.id
    
    await db.commit()
    
    # Create timeline entry
    timeline_entry = ScopeTimeline(
        project_id=scope_item.project_id,
        event_type="scope_removed",
        event_description=f"Removed scope item: {scope_item.name}",
        related_scope_id=scope_item.id,
        created_by_id=current_user.id,
        impact_summary={"type": "removal", "effort_estimate": scope_item.current_effort_estimate}
    )
    db.add(timeline_entry)
    await db.commit()
    
    return {"message": "Scope item deactivated successfully"}


# Change Request Endpoints
@router.get("/projects/{project_id}/change-requests", response_model=List[ChangeRequestSchema])
async def get_change_requests(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Get change requests for a project"""
    stmt = select(ChangeRequest).where(
        ChangeRequest.project_id == project_id
    )
    
    if status:
        stmt = stmt.where(ChangeRequest.status == status)
    
    if priority:
        stmt = stmt.where(ChangeRequest.priority == priority)
    
    stmt = stmt.order_by(ChangeRequest.requested_date.desc())
    stmt = stmt.offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    change_requests = result.scalars().all()
    
    return change_requests


@router.post("/projects/{project_id}/change-requests", response_model=ChangeRequestSchema)
async def create_change_request(
    project_id: str,
    request_data: ChangeRequestCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new change request"""
    if request_data.project_id != project_id:
        raise HTTPException(status_code=400, detail="Project ID mismatch")
    
    # Generate request number
    stmt = select(func.count(ChangeRequest.id)).where(ChangeRequest.project_id == project_id)
    result = await db.execute(stmt)
    count = result.scalar() or 0
    request_number = f"CR-{project_id[-6:]}-{count + 1:03d}"
    
    change_request = ChangeRequest(
        request_number=request_number,
        requested_by_id=current_user.id,
        **request_data.dict()
    )
    
    db.add(change_request)
    await db.commit()
    await db.refresh(change_request)
    
    # Create timeline entry
    timeline_entry = ScopeTimeline(
        project_id=project_id,
        event_type="change_request_created",
        event_description=f"Created change request: {change_request.title}",
        related_change_request_id=change_request.id,
        created_by_id=current_user.id,
        impact_summary={
            "type": "change_request",
            "change_type": change_request.change_type,
            "priority": change_request.priority
        }
    )
    db.add(timeline_entry)
    await db.commit()
    
    return change_request


@router.get("/change-requests/{request_id}", response_model=ChangeRequestSchema)
async def get_change_request(
    request_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific change request"""
    stmt = select(ChangeRequest).where(ChangeRequest.id == request_id)
    result = await db.execute(stmt)
    change_request = result.scalar_one_or_none()
    
    if not change_request:
        raise HTTPException(status_code=404, detail="Change request not found")
    
    return change_request


@router.put("/change-requests/{request_id}", response_model=ChangeRequestSchema)
async def update_change_request(
    request_id: str,
    request_data: ChangeRequestUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a change request"""
    stmt = select(ChangeRequest).where(ChangeRequest.id == request_id)
    result = await db.execute(stmt)
    change_request = result.scalar_one_or_none()
    
    if not change_request:
        raise HTTPException(status_code=404, detail="Change request not found")
    
    # Track status changes
    old_status = change_request.status
    
    for field, value in request_data.dict(exclude_unset=True).items():
        setattr(change_request, field, value)
    
    await db.commit()
    await db.refresh(change_request)
    
    # Create timeline entry for status changes
    if old_status != change_request.status:
        timeline_entry = ScopeTimeline(
            project_id=change_request.project_id,
            event_type="change_request_updated",
            event_description=f"Change request {change_request.request_number} status changed from {old_status} to {change_request.status}",
            related_change_request_id=change_request.id,
            created_by_id=current_user.id,
            impact_summary={"status_change": {"from": old_status, "to": change_request.status}}
        )
        db.add(timeline_entry)
        await db.commit()
    
    return change_request


@router.post("/change-requests/{request_id}/approve")
async def approve_change_request(
    request_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Approve a change request"""
    stmt = select(ChangeRequest).where(ChangeRequest.id == request_id)
    result = await db.execute(stmt)
    change_request = result.scalar_one_or_none()
    
    if not change_request:
        raise HTTPException(status_code=404, detail="Change request not found")
    
    if current_user.id not in change_request.approvers:
        raise HTTPException(status_code=403, detail="Not authorized to approve this request")
    
    # Add to approved list if not already there
    if current_user.id not in change_request.approved_by:
        change_request.approved_by = list(change_request.approved_by) + [current_user.id]
    
    # Check if all required approvers have approved
    if set(change_request.approved_by).issuperset(set(change_request.approvers)):
        change_request.status = "approved"
        change_request.approved_date = func.now()
    
    await db.commit()
    
    return {"message": "Change request approved", "status": change_request.status}


# Scope Timeline Endpoints
@router.get("/projects/{project_id}/scope-timeline", response_model=List[ScopeTimelineSchema])
async def get_scope_timeline(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    event_type: Optional[str] = Query(None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Get scope timeline for a project"""
    stmt = select(ScopeTimeline).where(
        ScopeTimeline.project_id == project_id
    )
    
    if event_type:
        stmt = stmt.where(ScopeTimeline.event_type == event_type)
    
    stmt = stmt.order_by(ScopeTimeline.event_date.desc())
    stmt = stmt.offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    timeline = result.scalars().all()
    
    return timeline


# Scope Baseline Endpoints
@router.get("/projects/{project_id}/baselines", response_model=List[ScopeBaselineSchema])
async def get_scope_baselines(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    is_active: bool = Query(default=True),
) -> Any:
    """Get scope baselines for a project"""
    stmt = select(ScopeBaseline).where(
        ScopeBaseline.project_id == project_id,
        ScopeBaseline.is_active == is_active
    ).order_by(ScopeBaseline.baseline_date.desc())
    
    result = await db.execute(stmt)
    baselines = result.scalars().all()
    
    return baselines


@router.post("/projects/{project_id}/baselines", response_model=ScopeBaselineSchema)
async def create_scope_baseline(
    project_id: str,
    baseline_data: ScopeBaselineCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new scope baseline"""
    if baseline_data.project_id != project_id:
        raise HTTPException(status_code=400, detail="Project ID mismatch")
    
    baseline = ScopeBaseline(
        created_by_id=current_user.id,
        **baseline_data.dict()
    )
    
    db.add(baseline)
    await db.commit()
    await db.refresh(baseline)
    
    return baseline


# Analysis and Reporting Endpoints
@router.get("/projects/{project_id}/scope-analysis", response_model=ScopeAnalysis)
async def get_scope_analysis(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get scope analysis for a project"""
    # Get scope statistics
    scope_stats_stmt = select(
        func.count(ProjectScope.id).label("total"),
        func.sum(func.case((ProjectScope.is_completed == True, 1), else_=0)).label("completed"),
        func.sum(func.case((ProjectScope.is_original_scope == True, 1), else_=0)).label("original"),
        func.sum(func.case((ProjectScope.is_original_scope == False, 1), else_=0)).label("added"),
        func.coalesce(func.sum(ProjectScope.current_effort_estimate), 0).label("total_estimated"),
        func.coalesce(func.sum(ProjectScope.actual_effort), 0).label("total_actual")
    ).where(
        ProjectScope.project_id == project_id,
        ProjectScope.is_active == True
    )
    
    result = await db.execute(scope_stats_stmt)
    stats = result.first()
    
    completion_percentage = (stats.completed / stats.total * 100) if stats.total > 0 else 0
    scope_change_percentage = (stats.added / stats.original * 100) if stats.original > 0 else 0
    effort_variance = ((stats.total_actual - stats.total_estimated) / stats.total_estimated * 100) if stats.total_estimated > 0 else 0
    
    return ScopeAnalysis(
        project_id=project_id,
        total_scope_items=stats.total,
        completed_scope_items=stats.completed,
        completion_percentage=completion_percentage,
        original_scope_count=stats.original,
        added_scope_count=stats.added,
        removed_scope_count=0,  # Would need additional query
        scope_change_percentage=scope_change_percentage,
        total_estimated_effort=float(stats.total_estimated),
        total_actual_effort=float(stats.total_actual),
        effort_variance_percentage=effort_variance,
        scope_health_status="healthy" if scope_change_percentage < 20 else "at_risk"
    )


@router.get("/projects/{project_id}/change-request-summary", response_model=ChangeRequestSummary)
async def get_change_request_summary(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get change request summary for a project"""
    # Get change request statistics
    cr_stats_stmt = select(
        func.count(ChangeRequest.id).label("total"),
        func.sum(func.case((ChangeRequest.status == "proposed", 1), else_=0)).label("pending"),
        func.sum(func.case((ChangeRequest.status == "approved", 1), else_=0)).label("approved"),
        func.sum(func.case((ChangeRequest.status == "rejected", 1), else_=0)).label("rejected"),
        func.sum(func.case((ChangeRequest.status == "implemented", 1), else_=0)).label("implemented"),
        func.coalesce(func.sum(ChangeRequest.time_impact_hours), 0).label("total_time"),
        func.coalesce(func.sum(ChangeRequest.cost_impact), 0).label("total_cost")
    ).where(ChangeRequest.project_id == project_id)
    
    result = await db.execute(cr_stats_stmt)
    stats = result.first()
    
    return ChangeRequestSummary(
        project_id=project_id,
        total_change_requests=stats.total,
        pending_requests=stats.pending,
        approved_requests=stats.approved,
        rejected_requests=stats.rejected,
        implemented_requests=stats.implemented,
        total_time_impact=float(stats.total_time),
        total_cost_impact=stats.total_cost,
        avg_approval_time_days=7.0  # Would calculate from actual data
    )


@router.get("/projects/{project_id}/scope-visual-data", response_model=ScopeVisualData)
async def get_scope_visual_data(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get data for scope visualization"""
    # Get scope items
    scope_stmt = select(ProjectScope).where(
        ProjectScope.project_id == project_id,
        ProjectScope.is_active == True
    )
    scope_result = await db.execute(scope_stmt)
    scope_items = scope_result.scalars().all()
    
    # Get timeline events
    timeline_stmt = select(ScopeTimeline).where(
        ScopeTimeline.project_id == project_id
    ).order_by(ScopeTimeline.event_date)
    timeline_result = await db.execute(timeline_stmt)
    timeline_events = timeline_result.scalars().all()
    
    # Separate original and current scope
    original_scope = [
        {
            "id": item.id,
            "name": item.name,
            "type": item.scope_type,
            "effort": item.original_effort_estimate or 0,
            "completed": item.is_completed
        }
        for item in scope_items if item.is_original_scope
    ]
    
    current_scope = [
        {
            "id": item.id,
            "name": item.name,
            "type": item.scope_type,
            "effort": item.current_effort_estimate or 0,
            "completed": item.is_completed,
            "is_original": item.is_original_scope
        }
        for item in scope_items
    ]
    
    # Format timeline
    timeline_data = [
        {
            "id": event.id,
            "date": event.event_date.isoformat(),
            "type": event.event_type,
            "description": event.event_description,
            "impact": event.impact_summary
        }
        for event in timeline_events
    ]
    
    return ScopeVisualData(
        original_scope=original_scope,
        current_scope=current_scope,
        scope_changes=[],  # Would calculate changes
        timeline_events=timeline_data,
        baseline_comparison={}  # Would compare with baselines
    )
