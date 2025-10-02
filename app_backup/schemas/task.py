from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime
from ..models.task import TaskStatus, TaskPriority, TaskType


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    task_type: TaskType = TaskType.TASK


class TaskCreate(TaskBase):
    project_id: str
    assignee_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    estimated_hours: Optional[float] = None
    story_points: Optional[int] = None
    labels: List[str] = []
    tags: List[str] = []


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    task_type: Optional[TaskType] = None
    assignee_id: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    story_points: Optional[int] = None
    labels: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class Task(TaskBase):
    id: str
    project_id: str
    assignee_id: Optional[str] = None
    created_by_id: str
    parent_task_id: Optional[str] = None
    position: int = 0
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    estimated_hours: Optional[float] = None
    actual_hours: float = 0.0
    story_points: Optional[int] = None
    labels: List[str] = []
    tags: List[str] = []
    custom_fields: Dict[str, Any] = {}
    task_metadata: Dict[str, Any] = {}
    is_recurring: bool = False
    is_template: bool = False
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
