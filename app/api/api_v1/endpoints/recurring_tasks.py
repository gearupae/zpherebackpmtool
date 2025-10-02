from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ....api.deps_tenant import get_tenant_db as get_db
from ....api.deps_tenant import get_current_active_user_master as get_current_active_user, get_current_organization_master as get_current_organization
from ....models.user import User
from ....models.organization import Organization
from ....models.project import Project
from ....models.task import Task
from ....models.recurring_task import RecurringTaskTemplate
from ....schemas.recurring_task import (
    RecurringTaskTemplateCreate, RecurringTaskTemplateUpdate, RecurringTaskTemplateResponse
)

router = APIRouter()


@router.get("/", response_model=List[RecurringTaskTemplateResponse])
async def get_recurring_templates(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get recurring task templates"""
    
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
        
        # Get project templates
        query = select(RecurringTaskTemplate).where(
            RecurringTaskTemplate.project_id == project_id
        ).offset(skip).limit(limit)
    else:
        # Get all templates for organization projects
        query = select(RecurringTaskTemplate).join(Project).where(
            Project.organization_id == current_org.id
        ).offset(skip).limit(limit)
    
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return templates


@router.post("/", response_model=RecurringTaskTemplateResponse)
async def create_recurring_template(
    template_in: RecurringTaskTemplateCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new recurring task template"""
    
    # Verify project access
    project_query = select(Project).where(
        and_(
            Project.id == template_in.project_id,
            Project.organization_id == current_org.id
        )
    )
    
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create template
    template = RecurringTaskTemplate(
        title=template_in.title,
        description=template_in.description,
        project_id=template_in.project_id,
        priority=template_in.priority,
        task_type=template_in.task_type,
        estimated_hours=template_in.estimated_hours,
        story_points=template_in.story_points,
        default_assignee_id=template_in.default_assignee_id,
        frequency=template_in.frequency,
        interval_value=template_in.interval_value,
        days_of_week=template_in.days_of_week or [],
        day_of_month=template_in.day_of_month,
        months_of_year=template_in.months_of_year or [],
        start_date=template_in.start_date,
        end_date=template_in.end_date,
        max_occurrences=template_in.max_occurrences,
        advance_creation_days=template_in.advance_creation_days,
        skip_weekends=template_in.skip_weekends,
        skip_holidays=template_in.skip_holidays,
        custom_fields=template_in.custom_fields or {},
        labels=template_in.labels or [],
        tags=template_in.tags or []
    )
    
    # Calculate next due date
    template.next_due_date = template.calculate_next_due_date(template.start_date)
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    return template


@router.get("/{template_id}", response_model=RecurringTaskTemplateResponse)
async def get_recurring_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get recurring task template by ID"""
    
    query = select(RecurringTaskTemplate).join(Project).where(
        and_(
            RecurringTaskTemplate.id == template_id,
            Project.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Recurring task template not found")
    
    return template


@router.put("/{template_id}", response_model=RecurringTaskTemplateResponse)
async def update_recurring_template(
    template_id: str,
    template_in: RecurringTaskTemplateUpdate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update recurring task template"""
    
    query = select(RecurringTaskTemplate).join(Project).where(
        and_(
            RecurringTaskTemplate.id == template_id,
            Project.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Recurring task template not found")
    
    # Update template fields
    for field, value in template_in.dict(exclude_unset=True).items():
        setattr(template, field, value)
    
    # Recalculate next due date if recurrence settings changed
    if any(field in template_in.dict(exclude_unset=True) for field in 
           ['frequency', 'interval_value', 'start_date']):
        template.next_due_date = template.calculate_next_due_date()
    
    await db.commit()
    await db.refresh(template)
    
    return template


@router.delete("/{template_id}")
async def delete_recurring_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Delete recurring task template"""
    
    query = select(RecurringTaskTemplate).join(Project).where(
        and_(
            RecurringTaskTemplate.id == template_id,
            Project.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Recurring task template not found")
    
    await db.delete(template)
    await db.commit()
    
    return {"message": "Recurring task template deleted successfully"}


@router.post("/{template_id}/generate")
async def generate_task_from_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Manually generate a task from recurring template"""
    
    query = select(RecurringTaskTemplate).join(Project).where(
        and_(
            RecurringTaskTemplate.id == template_id,
            Project.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Recurring task template not found")
    
    # Create task from template
    from datetime import datetime
    
    task = Task(
        title=template.title,
        description=template.description,
        project_id=template.project_id,
        priority=template.priority,
        task_type=template.task_type,
        assignee_id=template.default_assignee_id,
        created_by_id=current_user.id,
        estimated_hours=template.estimated_hours,
        story_points=template.story_points,
        labels=template.labels,
        tags=template.tags,
        custom_fields=template.custom_fields,
        recurring_template_id=template.id,
        is_recurring=True,
        due_date=template.next_due_date
    )
    
    db.add(task)
    
    # Update template tracking
    template.last_generated_date = datetime.utcnow()
    template.total_generated += 1
    template.next_due_date = template.calculate_next_due_date()
    
    await db.commit()
    await db.refresh(task)
    
    return {"message": "Task generated successfully", "task_id": task.id}


@router.post("/{template_id}/pause")
async def pause_recurring_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Pause recurring task template"""
    
    query = select(RecurringTaskTemplate).join(Project).where(
        and_(
            RecurringTaskTemplate.id == template_id,
            Project.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Recurring task template not found")
    
    template.is_paused = True
    await db.commit()
    
    return {"message": "Recurring task template paused"}


@router.post("/{template_id}/resume")
async def resume_recurring_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Resume recurring task template"""
    
    query = select(RecurringTaskTemplate).join(Project).where(
        and_(
            RecurringTaskTemplate.id == template_id,
            Project.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Recurring task template not found")
    
    template.is_paused = False
    await db.commit()
    
    return {"message": "Recurring task template resumed"}
