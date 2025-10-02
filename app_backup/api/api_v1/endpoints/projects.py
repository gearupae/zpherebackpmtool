from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ....models.user import User
from ....models.project import Project as ProjectModel, ProjectMember
from ....schemas.project import Project, ProjectCreate, ProjectUpdate
from ...deps import get_current_active_user
from ....db.database import get_db
import uuid
import re

router = APIRouter()


def create_slug(name: str) -> str:
    """Create a URL-friendly slug from project name"""
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


@router.get("/", response_model=List[Project])
async def get_projects(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get all projects for current organization"""
    # Query projects where user is a member or owner
    query = select(ProjectModel).where(
        (ProjectModel.organization_id == current_user.organization_id) &
        (ProjectModel.is_archived == False)
    ).order_by(ProjectModel.updated_at.desc())
    
    result = await db.execute(query)
    projects = result.scalars().all()
    
    return projects


@router.post("/", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new project"""
    # Generate slug if not provided
    if not project_data.slug:
        project_data.slug = create_slug(project_data.name)
    
    # Check if slug already exists in organization
    existing_query = select(ProjectModel).where(
        (ProjectModel.slug == project_data.slug) &
        (ProjectModel.organization_id == current_user.organization_id)
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project with this slug already exists"
        )
    
    # Create project
    project = ProjectModel(
        id=str(uuid.uuid4()),
        organization_id=current_user.organization_id,
        owner_id=current_user.id,
        **project_data.model_dump()
    )
    
    db.add(project)
    await db.flush()
    
    # Add creator as project owner
    project_member = ProjectMember(
        id=str(uuid.uuid4()),
        project_id=project.id,
        user_id=current_user.id,
        role="owner",
        can_edit_project=True,
        can_create_tasks=True,
        can_assign_tasks=True,
        can_delete_tasks=True
    )
    
    db.add(project_member)
    await db.commit()
    await db.refresh(project)
    
    return project


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get a specific project"""
    query = select(ProjectModel).where(
        (ProjectModel.id == project_id) &
        (ProjectModel.organization_id == current_user.organization_id)
    )
    
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


@router.put("/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update a project"""
    query = select(ProjectModel).where(
        (ProjectModel.id == project_id) &
        (ProjectModel.organization_id == current_user.organization_id)
    )
    
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Update project fields
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    await db.commit()
    await db.refresh(project)
    
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Archive a project (soft delete)"""
    query = select(ProjectModel).where(
        (ProjectModel.id == project_id) &
        (ProjectModel.organization_id == current_user.organization_id)
    )
    
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Soft delete by archiving
    project.is_archived = True
    await db.commit()
