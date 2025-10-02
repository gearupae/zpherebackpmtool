from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from sqlalchemy.orm import selectinload
import uuid
from datetime import datetime

from ....db.database import get_db
from ....models.user import User
from ....models.task import Task
from ....models.task_assignee import TaskAssignee
from ....models.project import Project
from ....models.organization import Organization
from ....schemas.task_assignee import TaskAssigneeCreate, TaskAssigneeUpdate, TaskAssignee as TaskAssigneeSchema
from ...deps import get_current_active_user, get_current_organization
from ...deps_tenant import get_tenant_db
from ....db.tenant_manager import tenant_manager
from sqlalchemy import select as sa_select

router = APIRouter()


@router.get("/tasks/{task_id}/assignees", response_model=List[TaskAssigneeSchema])
async def get_task_assignees(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get all assignees for a task"""
    
    # Verify task exists and user has access
    task_result = await db.execute(
        select(Task)
        .join(Project)
        .where(
            and_(
                Task.id == task_id,
                Project.organization_id == current_org.id
            )
        )
    )
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Get assignees with user info
    assignees_result = await db.execute(
        select(TaskAssignee)
        .options(
            selectinload(TaskAssignee.user),
            selectinload(TaskAssignee.assigned_by)
        )
        .where(TaskAssignee.task_id == task_id)
        .order_by(TaskAssignee.is_primary.desc(), TaskAssignee.created_at.asc())
    )
    assignees = assignees_result.scalars().all()
    
    return assignees


@router.post("/tasks/{task_id}/assignees", response_model=TaskAssigneeSchema, status_code=status.HTTP_201_CREATED)
async def add_task_assignee(
    task_id: str,
    assignee_data: TaskAssigneeCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Add an assignee to a task"""
    
    # Verify task exists and user has access
    task_result = await db.execute(
        select(Task)
        .join(Project)
        .where(
            and_(
                Task.id == task_id,
                Project.organization_id == current_org.id
            )
        )
    )
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Verify assignee user exists and is in the same organization
    user_result = await db.execute(
        select(User).where(
            and_(
                User.id == assignee_data.user_id,
                User.organization_id == current_org.id
            )
        )
    )
    assignee_user = user_result.scalar_one_or_none()
    
    if not assignee_user:
        # Attempt to replicate from master DB if user exists there
        try:
            master_session = await tenant_manager.get_master_session()
            try:
                mu_res = await master_session.execute(sa_select(User).where(
                    and_(User.id == assignee_data.user_id, User.organization_id == current_org.id)
                ))
                mu = mu_res.scalar_one_or_none()
                if mu:
                    db.add(User(
                        id=mu.id,
                        email=mu.email,
                        username=mu.username,
                        first_name=mu.first_name,
                        last_name=mu.last_name,
                        hashed_password=mu.hashed_password,
                        organization_id=mu.organization_id,
                        role=mu.role,
                        status=mu.status,
                        is_active=mu.is_active,
                        is_verified=mu.is_verified,
                        timezone=mu.timezone,
                        phone=mu.phone,
                        bio=mu.bio,
                        preferences=mu.preferences,
                        notification_settings=mu.notification_settings,
                        last_login=mu.last_login,
                        password_changed_at=mu.password_changed_at,
                    ))
                    await db.flush()
                    assignee_user = mu  # proceed after replication
            finally:
                await master_session.close()
        except Exception:
            pass

    if not assignee_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or not in the same organization"
        )
    
    # Check if user is already assigned
    existing_assignee = await db.execute(
        select(TaskAssignee).where(
            and_(
                TaskAssignee.task_id == task_id,
                TaskAssignee.user_id == assignee_data.user_id
            )
        )
    )
    if existing_assignee.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already assigned to this task"
        )
    
    # If this is set as primary, unset other primary assignees
    if assignee_data.is_primary:
        # Unset existing primary assignees for this task
        await db.execute(
            update(TaskAssignee)
            .where(TaskAssignee.task_id == task_id)
            .values(is_primary=False)
        )
    
    # Create task assignee
    task_assignee = TaskAssignee(
        id=str(uuid.uuid4()),
        task_id=task_id,
        user_id=assignee_data.user_id,
        is_primary=assignee_data.is_primary,
        assigned_at=datetime.utcnow(),
        assigned_by_id=current_user.id
    )
    
    db.add(task_assignee)
    await db.commit()
    await db.refresh(task_assignee)
    
    # Load user info
    await db.refresh(task_assignee, ["user", "assigned_by"])
    
    return task_assignee


@router.put("/tasks/{task_id}/assignees/{assignee_id}", response_model=TaskAssigneeSchema)
async def update_task_assignee(
    task_id: str,
    assignee_id: str,
    assignee_data: TaskAssigneeUpdate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a task assignee"""
    
    # Get assignee and verify permissions
    assignee_result = await db.execute(
        select(TaskAssignee)
        .options(
            selectinload(TaskAssignee.user),
            selectinload(TaskAssignee.assigned_by)
        )
        .join(Task)
        .join(Project)
        .where(
            and_(
                TaskAssignee.id == assignee_id,
                TaskAssignee.task_id == task_id,
                Project.organization_id == current_org.id
            )
        )
    )
    assignee = assignee_result.scalar_one_or_none()
    
    if not assignee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task assignee not found"
        )
    
    # If setting as primary, unset other primary assignees
    if assignee_data.is_primary is True:
        # Unset other primary assignees for this task
        await db.execute(
            update(TaskAssignee)
            .where(
                and_(
                    TaskAssignee.task_id == task_id,
                    TaskAssignee.id != assignee_id
                )
            )
            .values(is_primary=False)
        )
    
    # Update assignee
    if assignee_data.is_primary is not None:
        assignee.is_primary = assignee_data.is_primary
    
    await db.commit()
    await db.refresh(assignee)
    
    return assignee


@router.delete("/tasks/{task_id}/assignees/{assignee_id}")
async def remove_task_assignee(
    task_id: str,
    assignee_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Remove an assignee from a task"""
    
    # Get assignee and verify permissions
    assignee_result = await db.execute(
        select(TaskAssignee)
        .join(Task)
        .join(Project)
        .where(
            and_(
                TaskAssignee.id == assignee_id,
                TaskAssignee.task_id == task_id,
                Project.organization_id == current_org.id
            )
        )
    )
    assignee = assignee_result.scalar_one_or_none()
    
    if not assignee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task assignee not found"
        )
    
    # Remove assignee
    await db.delete(assignee)
    await db.commit()
    
    return {"message": "Assignee removed successfully"}
