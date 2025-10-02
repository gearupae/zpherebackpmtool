from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from datetime import datetime

from ....db.database import get_db
from ....models.user import User
from ....models.organization import Organization
from ....models.handoff_summary import HandoffSummary, HandoffStatus
from ....models.project import Project
from ....models.task import Task
from ....schemas.handoff_summary import (
    HandoffSummaryCreate,
    HandoffSummaryUpdate,
    HandoffSummary as HandoffSummarySchema,
    HandoffSummaryResponse
)
from ...deps import get_current_active_user, get_current_organization

router = APIRouter()


@router.post("/", response_model=HandoffSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_handoff_summary(
    handoff_data: HandoffSummaryCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new handoff summary"""
    # Verify project belongs to organization
    project_result = await db.execute(
        select(Project).where(
            and_(
                Project.id == handoff_data.project_id,
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

    # Verify task belongs to project if specified
    if handoff_data.task_id:
        task_result = await db.execute(
            select(Task).where(
                and_(
                    Task.id == handoff_data.task_id,
                    Task.project_id == handoff_data.project_id
                )
            )
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

    # Verify to_user exists and belongs to organization
    to_user_result = await db.execute(
        select(User).where(
            and_(
                User.id == handoff_data.to_user_id,
                User.organization_id == current_org.id
            )
        )
    )
    to_user = to_user_result.scalar_one_or_none()
    if not to_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found"
        )

    # Create handoff summary
    handoff_summary = HandoffSummary(
        **handoff_data.model_dump(),
        from_user_id=current_user.id,
        auto_generated=False,  # Manual creation
        generation_source="manual"
    )
    
    db.add(handoff_summary)
    await db.commit()
    await db.refresh(handoff_summary)
    
    return await _enrich_handoff_response(handoff_summary, db)


@router.get("/", response_model=List[HandoffSummaryResponse])
async def get_handoff_summaries(
    project_id: str = None,
    task_id: str = None,
    from_user_id: str = None,
    to_user_id: str = None,
    status: HandoffStatus = None,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get handoff summaries with filtering"""
    query = select(HandoffSummary).options(
        selectinload(HandoffSummary.project),
        selectinload(HandoffSummary.task),
        selectinload(HandoffSummary.from_user),
        selectinload(HandoffSummary.to_user),
        selectinload(HandoffSummary.reviewed_by)
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
        conditions.append(HandoffSummary.project_id == project_id)
    else:
        # Filter by organization's projects
        org_projects_subquery = select(Project.id).where(
            Project.organization_id == current_org.id
        )
        conditions.append(HandoffSummary.project_id.in_(org_projects_subquery))
    
    if task_id:
        conditions.append(HandoffSummary.task_id == task_id)
        
    if from_user_id:
        conditions.append(HandoffSummary.from_user_id == from_user_id)
        
    if to_user_id:
        conditions.append(HandoffSummary.to_user_id == to_user_id)
        
    if status:
        conditions.append(HandoffSummary.status == status)
    
    # Show handoffs involving current user
    conditions.append(
        or_(
            HandoffSummary.from_user_id == current_user.id,
            HandoffSummary.to_user_id == current_user.id
        )
    )
    
    query = query.where(and_(*conditions)).order_by(HandoffSummary.handoff_date.desc())
    
    result = await db.execute(query)
    handoff_summaries = result.scalars().all()
    
    return [await _enrich_handoff_response(handoff, db) for handoff in handoff_summaries]


@router.get("/{handoff_id}", response_model=HandoffSummaryResponse)
async def get_handoff_summary(
    handoff_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get a specific handoff summary"""
    handoff_summary = await _get_handoff_or_404(handoff_id, current_user.id, current_org.id, db)
    return await _enrich_handoff_response(handoff_summary, db)


@router.put("/{handoff_id}", response_model=HandoffSummaryResponse)
async def update_handoff_summary(
    handoff_id: str,
    handoff_update: HandoffSummaryUpdate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update a handoff summary"""
    handoff_summary = await _get_handoff_or_404(handoff_id, current_user.id, current_org.id, db)
    
    # Update handoff summary
    for field, value in handoff_update.model_dump(exclude_unset=True).items():
        setattr(handoff_summary, field, value)
    
    await db.commit()
    await db.refresh(handoff_summary)
    
    return await _enrich_handoff_response(handoff_summary, db)


@router.post("/{handoff_id}/complete", response_model=HandoffSummaryResponse)
async def complete_handoff(
    handoff_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Mark handoff as completed"""
    handoff_summary = await _get_handoff_or_404(handoff_id, current_user.id, current_org.id, db)
    
    # Only to_user can complete the handoff
    if handoff_summary.to_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the target user can complete the handoff"
        )
    
    handoff_summary.status = HandoffStatus.COMPLETED
    handoff_summary.actual_completion_date = datetime.utcnow()
    
    await db.commit()
    await db.refresh(handoff_summary)
    
    return await _enrich_handoff_response(handoff_summary, db)


@router.post("/{handoff_id}/review", response_model=HandoffSummaryResponse)
async def review_handoff(
    handoff_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Review and approve handoff"""
    handoff_summary = await _get_handoff_or_404(handoff_id, current_user.id, current_org.id, db)
    
    handoff_summary.reviewed_by_id = current_user.id
    handoff_summary.reviewed_at = datetime.utcnow()
    handoff_summary.status = HandoffStatus.PENDING_REVIEW
    
    await db.commit()
    await db.refresh(handoff_summary)
    
    return await _enrich_handoff_response(handoff_summary, db)


@router.post("/auto-generate", response_model=HandoffSummaryResponse)
async def auto_generate_handoff(
    project_id: str,
    task_id: str = None,
    to_user_id: str = None,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Auto-generate handoff summary based on project/task context"""
    # Verify project and task
    project_result = await db.execute(
        select(Project).where(
            and_(
                Project.id == project_id,
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

    task = None
    if task_id:
        task_result = await db.execute(
            select(Task).where(
                and_(
                    Task.id == task_id,
                    Task.project_id == project_id
                )
            )
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

    # Auto-generate context summary
    context_summary = f"Auto-generated handoff for {project.name}"
    if task:
        context_summary += f" - {task.title}"
    
    context_summary += f"\n\nProject Status: {project.status}"
    context_summary += f"\nProject Description: {project.description or 'No description available'}"
    
    if task:
        context_summary += f"\n\nTask Status: {task.status}"
        context_summary += f"\nTask Description: {task.description or 'No description available'}"

    # Create auto-generated handoff
    handoff_data = {
        "title": f"Auto-generated handoff: {project.name}",
        "handoff_type": "task_assignment" if task else "project_transfer",
        "project_id": project_id,
        "task_id": task_id,
        "to_user_id": to_user_id or current_user.id,
        "context_summary": context_summary,
        "auto_generated": True,
        "generation_source": "auto_generate_api",
        "confidence_score": "medium"
    }
    
    handoff_summary = HandoffSummary(
        **handoff_data,
        from_user_id=current_user.id
    )
    
    db.add(handoff_summary)
    await db.commit()
    await db.refresh(handoff_summary)
    
    return await _enrich_handoff_response(handoff_summary, db)


async def _get_handoff_or_404(
    handoff_id: str, 
    current_user_id: str,
    organization_id: str, 
    db: AsyncSession
) -> HandoffSummary:
    """Get handoff or raise 404"""
    result = await db.execute(
        select(HandoffSummary)
        .options(
            selectinload(HandoffSummary.project),
            selectinload(HandoffSummary.task),
            selectinload(HandoffSummary.from_user),
            selectinload(HandoffSummary.to_user),
            selectinload(HandoffSummary.reviewed_by)
        )
        .join(Project)
        .where(
            and_(
                HandoffSummary.id == handoff_id,
                Project.organization_id == organization_id,
                or_(
                    HandoffSummary.from_user_id == current_user_id,
                    HandoffSummary.to_user_id == current_user_id
                )
            )
        )
    )
    handoff_summary = result.scalar_one_or_none()
    if not handoff_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handoff summary not found"
        )
    return handoff_summary


async def _enrich_handoff_response(
    handoff_summary: HandoffSummary, 
    db: AsyncSession
) -> HandoffSummaryResponse:
    """Enrich handoff summary with additional data"""
    response_data = {
        **handoff_summary.__dict__,
        "from_user_name": None,
        "to_user_name": None,
        "project_name": None,
        "task_title": None,
        "reviewed_by_name": None,
    }
    
    if handoff_summary.from_user:
        response_data["from_user_name"] = f"{handoff_summary.from_user.first_name} {handoff_summary.from_user.last_name}"
    
    if handoff_summary.to_user:
        response_data["to_user_name"] = f"{handoff_summary.to_user.first_name} {handoff_summary.to_user.last_name}"
    
    if handoff_summary.project:
        response_data["project_name"] = handoff_summary.project.name
    
    if handoff_summary.task:
        response_data["task_title"] = handoff_summary.task.title
        
    if handoff_summary.reviewed_by:
        response_data["reviewed_by_name"] = f"{handoff_summary.reviewed_by.first_name} {handoff_summary.reviewed_by.last_name}"
    
    return HandoffSummaryResponse(**response_data)





