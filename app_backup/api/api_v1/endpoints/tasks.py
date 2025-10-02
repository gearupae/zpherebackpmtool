from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from ....models.user import User
from ....models.task import Task as TaskModel, TaskStatus, TaskPriority, TaskType
from ....models.project import Project
from ....schemas.task import Task, TaskCreate, TaskUpdate
from ...deps import get_current_active_user
from ....db.database import get_db
import uuid

router = APIRouter()


@router.get("/", response_model=List[Task])
async def get_tasks(
    current_user: User = Depends(get_current_active_user),
    project_id: str = None,
    status: TaskStatus = None,
    priority: TaskPriority = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get all tasks for current user with optional filters"""
    
    # Build query based on filters
    query = select(TaskModel).join(Project).where(
        Project.organization_id == current_user.organization_id
    )
    
    if project_id:
        query = query.where(TaskModel.project_id == project_id)
    
    if status:
        query = query.where(TaskModel.status == status)
    
    if priority:
        query = query.where(TaskModel.priority == priority)
    
    # Order by priority and due date
    query = query.order_by(TaskModel.priority.desc(), TaskModel.due_date.asc())
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    return tasks


@router.post("/", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new task"""
    
    # Verify project exists and user has access
    project_query = select(Project).where(
        (Project.id == task_data.project_id) &
        (Project.organization_id == current_user.organization_id)
    )
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Create task
    task = TaskModel(
        id=str(uuid.uuid4()),
        created_by_id=current_user.id,
        **task_data.model_dump()
    )
    
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    return task


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get a specific task"""
    
    query = select(TaskModel).join(Project).where(
        (TaskModel.id == task_id) &
        (Project.organization_id == current_user.organization_id)
    )
    
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return task


@router.put("/{task_id}", response_model=Task)
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update a task"""
    
    query = select(TaskModel).join(Project).where(
        (TaskModel.id == task_id) &
        (Project.organization_id == current_user.organization_id)
    )
    
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Update task fields
    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    await db.commit()
    await db.refresh(task)
    
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Archive a task (soft delete)"""
    
    query = select(TaskModel).join(Project).where(
        (TaskModel.id == task_id) &
        (Project.organization_id == current_user.organization_id)
    )
    
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Soft delete by archiving
    task.is_archived = True
    await db.commit()


@router.get("/my-tasks", response_model=List[Task])
async def get_my_tasks(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get tasks assigned to current user"""
    
    query = select(TaskModel).join(Project).where(
        (TaskModel.assignee_id == current_user.id) &
        (Project.organization_id == current_user.organization_id) &
        (TaskModel.is_archived == False)
    ).order_by(TaskModel.priority.desc(), TaskModel.due_date.asc())
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    return tasks
