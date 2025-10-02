from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ....api.deps_tenant import get_tenant_db as get_db
from ...deps_tenant import get_current_active_user_master as get_current_active_user, get_current_organization_master as get_current_organization
from ....models.user import User
from ....models.organization import Organization
from ....models.project import Project
from ....models.milestone import Milestone
from ....schemas.milestone import MilestoneCreate, MilestoneUpdate, MilestoneResponse

router = APIRouter()


@router.get("/", response_model=List[MilestoneResponse])
async def get_milestones(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get milestones, optionally filtered by project"""
    
    if project_id:
        # Verify project access
        project_query = select(Project).where(
            and_(
                Project.id == project_id,
                Project.organization_id == current_org.id
            )
        )
        
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get project milestones
        query = select(Milestone).where(
            Milestone.project_id == project_id
        ).offset(skip).limit(limit)
    else:
        # Get all milestones for organization projects
        query = select(Milestone).join(Project).where(
            Project.organization_id == current_org.id
        ).offset(skip).limit(limit)
    
    result = await db.execute(query)
    milestones = result.scalars().all()
    
    return milestones


@router.post("/", response_model=MilestoneResponse)
async def create_milestone(
    milestone_in: MilestoneCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new milestone"""
    
    # Verify project access
    project_query = select(Project).where(
        and_(
            Project.id == milestone_in.project_id,
            Project.organization_id == current_org.id
        )
    )
    
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create milestone
    milestone = Milestone(
        name=milestone_in.name,
        description=milestone_in.description,
        project_id=milestone_in.project_id,
        due_date=milestone_in.due_date,
        completion_criteria=milestone_in.completion_criteria or [],
        associated_tasks=milestone_in.associated_tasks or [],
        color=milestone_in.color,
        icon=milestone_in.icon,
        is_critical=milestone_in.is_critical
    )
    
    db.add(milestone)
    await db.commit()
    await db.refresh(milestone)
    
    return milestone


@router.get("/{milestone_id}", response_model=MilestoneResponse)
async def get_milestone(
    milestone_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get milestone by ID"""
    
    query = select(Milestone).join(Project).where(
        and_(
            Milestone.id == milestone_id,
            Project.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    milestone = result.scalar_one_or_none()
    
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    
    return milestone


@router.put("/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    milestone_id: str,
    milestone_in: MilestoneUpdate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update milestone"""
    
    query = select(Milestone).join(Project).where(
        and_(
            Milestone.id == milestone_id,
            Project.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    milestone = result.scalar_one_or_none()
    
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    
    # Update milestone fields
    for field, value in milestone_in.dict(exclude_unset=True).items():
        setattr(milestone, field, value)
    
    await db.commit()
    await db.refresh(milestone)
    
    return milestone


@router.delete("/{milestone_id}")
async def delete_milestone(
    milestone_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Delete milestone"""
    
    query = select(Milestone).join(Project).where(
        and_(
            Milestone.id == milestone_id,
            Project.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    milestone = result.scalar_one_or_none()
    
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    
    await db.delete(milestone)
    await db.commit()
    
    return {"message": "Milestone deleted successfully"}


@router.post("/{milestone_id}/complete")
async def complete_milestone(
    milestone_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Mark milestone as completed"""
    
    query = select(Milestone).join(Project).where(
        and_(
            Milestone.id == milestone_id,
            Project.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    milestone = result.scalar_one_or_none()
    
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    
    from datetime import datetime
    milestone.status = "completed"
    milestone.completed_date = datetime.utcnow()
    
    await db.commit()
    await db.refresh(milestone)
    
    return milestone
