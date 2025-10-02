from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from ....api.deps_tenant import get_tenant_db as get_db
from ...deps_tenant import get_current_active_user_master as get_current_active_user, get_current_organization_master as get_current_organization
from ....models.user import User
from ....models.organization import Organization
from ....models.project import Project
from ....models.task import Task, TaskDependency
from ....schemas.task_dependency import (
    TaskDependencyCreate, TaskDependencyResponse
)

router = APIRouter()


@router.get("/{task_id}/dependencies", response_model=List[TaskDependencyResponse])
async def get_task_dependencies(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get all dependencies for a task (both blocking and blocked by)"""
    
    # Verify task access
    task_query = select(Task).join(Project).where(
        and_(
            Task.id == task_id,
            Project.organization_id == current_org.id
        )
    )
    
    task_result = await db.execute(task_query)
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get all dependencies where this task is involved
    dependencies_query = select(TaskDependency).where(
        or_(
            TaskDependency.prerequisite_task_id == task_id,
            TaskDependency.dependent_task_id == task_id
        )
    )
    
    result = await db.execute(dependencies_query)
    dependencies = result.scalars().all()
    
    return dependencies


@router.post("/{task_id}/dependencies", response_model=TaskDependencyResponse)
async def create_task_dependency(
    task_id: str,
    dependency_in: TaskDependencyCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new task dependency"""
    
    # Verify both tasks exist and belong to organization
    tasks_query = select(Task).join(Project).where(
        and_(
            Task.id.in_([task_id, dependency_in.dependent_task_id]),
            Project.organization_id == current_org.id
        )
    )
    
    tasks_result = await db.execute(tasks_query)
    tasks = tasks_result.scalars().all()
    
    if len(tasks) != 2:
        raise HTTPException(status_code=404, detail="One or both tasks not found")
    
    # Check for circular dependencies
    if await _would_create_circular_dependency(task_id, dependency_in.dependent_task_id, db):
        raise HTTPException(status_code=400, detail="This dependency would create a circular dependency")
    
    # Check if dependency already exists
    existing_query = select(TaskDependency).where(
        and_(
            TaskDependency.prerequisite_task_id == task_id,
            TaskDependency.dependent_task_id == dependency_in.dependent_task_id
        )
    )
    
    existing_result = await db.execute(existing_query)
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Dependency already exists")
    
    # Create dependency
    dependency = TaskDependency(
        prerequisite_task_id=task_id,
        dependent_task_id=dependency_in.dependent_task_id,
        dependency_type=dependency_in.dependency_type
    )
    
    db.add(dependency)
    await db.commit()
    await db.refresh(dependency)
    
    return dependency


@router.delete("/{task_id}/dependencies/{dependency_id}")
async def remove_task_dependency(
    task_id: str,
    dependency_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Remove a task dependency"""
    
    # Verify task access
    task_query = select(Task).join(Project).where(
        and_(
            Task.id == task_id,
            Project.organization_id == current_org.id
        )
    )
    
    task_result = await db.execute(task_query)
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Find and delete dependency
    dependency_query = select(TaskDependency).where(
        and_(
            TaskDependency.id == dependency_id,
            or_(
                TaskDependency.prerequisite_task_id == task_id,
                TaskDependency.dependent_task_id == task_id
            )
        )
    )
    
    dependency_result = await db.execute(dependency_query)
    dependency = dependency_result.scalar_one_or_none()
    
    if not dependency:
        raise HTTPException(status_code=404, detail="Dependency not found")
    
    await db.delete(dependency)
    await db.commit()
    
    return {"message": "Dependency removed successfully"}


@router.get("/{task_id}/blockers", response_model=List[str])
async def get_task_blockers(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get all tasks that are blocking this task from being completed"""
    
    # Verify task access
    task_query = select(Task).join(Project).where(
        and_(
            Task.id == task_id,
            Project.organization_id == current_org.id
        )
    )
    
    task_result = await db.execute(task_query)
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get all tasks that block this one
    blockers_query = select(TaskDependency.prerequisite_task_id).where(
        and_(
            TaskDependency.dependent_task_id == task_id,
            TaskDependency.dependency_type == "blocks"
        )
    )
    
    result = await db.execute(blockers_query)
    blocker_ids = result.scalars().all()
    
    return blocker_ids


@router.get("/{task_id}/blocking", response_model=List[str])
async def get_tasks_blocked_by(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get all tasks that are blocked by this task"""
    
    # Verify task access
    task_query = select(Task).join(Project).where(
        and_(
            Task.id == task_id,
            Project.organization_id == current_org.id
        )
    )
    
    task_result = await db.execute(task_query)
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get all tasks blocked by this one
    blocked_query = select(TaskDependency.dependent_task_id).where(
        and_(
            TaskDependency.prerequisite_task_id == task_id,
            TaskDependency.dependency_type == "blocks"
        )
    )
    
    result = await db.execute(blocked_query)
    blocked_ids = result.scalars().all()
    
    return blocked_ids


async def _would_create_circular_dependency(
    prerequisite_id: str,
    dependent_id: str,
    db: AsyncSession,
    visited: set = None
) -> bool:
    """Check if creating a dependency would create a circular dependency"""
    
    if visited is None:
        visited = set()
    
    if prerequisite_id in visited:
        return True
    
    visited.add(prerequisite_id)
    
    # Check if dependent_id already depends on prerequisite_id (which would create a circle)
    dependencies_query = select(TaskDependency.prerequisite_task_id).where(
        TaskDependency.dependent_task_id == prerequisite_id
    )
    
    result = await db.execute(dependencies_query)
    parent_ids = result.scalars().all()
    
    for parent_id in parent_ids:
        if parent_id == dependent_id:
            return True
        if await _would_create_circular_dependency(parent_id, dependent_id, db, visited.copy()):
            return True
    
    return False
