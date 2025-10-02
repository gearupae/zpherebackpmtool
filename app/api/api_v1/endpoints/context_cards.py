from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from ....api.deps_tenant import get_tenant_db as get_db
from ....models.user import User
from ....models.organization import Organization
from ....models.context_card import ContextCard
from ....models.project import Project
from ....models.task import Task
from ....schemas.context_card import (
    ContextCardCreate,
    ContextCardUpdate,
    ContextCard as ContextCardSchema,
    ContextCardResponse
)
from ...deps import get_current_active_user, get_current_organization
from ...deps_tenant import get_tenant_db

router = APIRouter()


@router.post("/", response_model=ContextCardResponse, status_code=status.HTTP_201_CREATED)
async def create_context_card(
    context_card_data: ContextCardCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new context card"""
    # Verify project belongs to organization
    project_result = await db.execute(
        select(Project).where(
            and_(
                Project.id == context_card_data.project_id,
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
    if context_card_data.task_id:
        task_result = await db.execute(
            select(Task).where(
                and_(
                    Task.id == context_card_data.task_id,
                    Task.project_id == context_card_data.project_id
                )
            )
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

    # Create context card
    context_card = ContextCard(
        **context_card_data.model_dump(),
        created_by_id=current_user.id
    )
    
    db.add(context_card)
    await db.commit()
    await db.refresh(context_card)
    
    return await _enrich_context_card_response(context_card, db)


@router.get("/", response_model=List[ContextCardResponse])
async def get_context_cards(
    project_id: str = None,
    task_id: str = None,
    context_type: str = None,
    is_active: bool = True,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get context cards with filtering"""
    query = select(ContextCard).options(
        selectinload(ContextCard.project),
        selectinload(ContextCard.task),
        selectinload(ContextCard.created_by)
    )
    
    conditions = [ContextCard.is_active == is_active]
    
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
        conditions.append(ContextCard.project_id == project_id)
    else:
        # Filter by organization's projects
        org_projects_subquery = select(Project.id).where(
            Project.organization_id == current_org.id
        )
        conditions.append(ContextCard.project_id.in_(org_projects_subquery))
    
    if task_id:
        conditions.append(ContextCard.task_id == task_id)
        
    if context_type:
        conditions.append(ContextCard.context_type == context_type)
    
    query = query.where(and_(*conditions)).order_by(ContextCard.created_at.desc())
    
    result = await db.execute(query)
    context_cards = result.scalars().all()
    
    return [await _enrich_context_card_response(card, db) for card in context_cards]


@router.get("/{context_card_id}", response_model=ContextCardResponse)
async def get_context_card(
    context_card_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific context card"""
    context_card = await _get_context_card_or_404(context_card_id, current_org.id, db)
    return await _enrich_context_card_response(context_card, db)


@router.put("/{context_card_id}", response_model=ContextCardResponse)
async def update_context_card(
    context_card_id: str,
    context_card_update: ContextCardUpdate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a context card"""
    context_card = await _get_context_card_or_404(context_card_id, current_org.id, db)
    
    # Update context card
    for field, value in context_card_update.model_dump(exclude_unset=True).items():
        setattr(context_card, field, value)
    
    await db.commit()
    await db.refresh(context_card)
    
    return await _enrich_context_card_response(context_card, db)


@router.delete("/{context_card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_context_card(
    context_card_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> None:
    """Delete a context card (soft delete)"""
    context_card = await _get_context_card_or_404(context_card_id, current_org.id, db)
    
    context_card.is_active = False
    context_card.is_archived = True
    
    await db.commit()


@router.post("/{context_card_id}/auto-capture", response_model=ContextCardResponse)
async def auto_capture_context(
    context_card_id: str,
    trigger_event: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Mark a context card as auto-captured with trigger event"""
    context_card = await _get_context_card_or_404(context_card_id, current_org.id, db)
    
    context_card.auto_captured = True
    context_card.trigger_event = trigger_event
    
    await db.commit()
    await db.refresh(context_card)
    
    return await _enrich_context_card_response(context_card, db)


async def _get_context_card_or_404(
    context_card_id: str, 
    organization_id: str, 
    db: AsyncSession
) -> ContextCard:
    """Get context card or raise 404"""
    result = await db.execute(
        select(ContextCard)
        .options(
            selectinload(ContextCard.project),
            selectinload(ContextCard.task),
            selectinload(ContextCard.created_by)
        )
        .join(Project)
        .where(
            and_(
                ContextCard.id == context_card_id,
                Project.organization_id == organization_id
            )
        )
    )
    context_card = result.scalar_one_or_none()
    if not context_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Context card not found"
        )
    return context_card


async def _enrich_context_card_response(
    context_card: ContextCard, 
    db: AsyncSession
) -> ContextCardResponse:
    """Enrich context card with additional data"""
    response_data = {
        **context_card.__dict__,
        "created_by_name": None,
        "project_name": None,
        "task_title": None,
    }
    
    if context_card.created_by:
        response_data["created_by_name"] = f"{context_card.created_by.first_name} {context_card.created_by.last_name}"
    
    if context_card.project:
        response_data["project_name"] = context_card.project.name
    
    if context_card.task:
        response_data["task_title"] = context_card.task.title
    
    return ContextCardResponse(**response_data)





