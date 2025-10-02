from typing import Dict, Any, Optional, List
from pydantic import BaseModel, field_validator
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
    # Sprint
    sprint_name: Optional[str] = None
    sprint_start_date: Optional[datetime] = None
    sprint_end_date: Optional[datetime] = None
    sprint_goal: Optional[str] = None
    # Estimates
    estimated_hours: Optional[float] = None
    story_points: Optional[int] = None
    labels: List[str] = []
    tags: List[str] = []
    visible_to_customer: Optional[bool] = False

    # Coerce empty strings to None for optional datetime fields
    @field_validator('start_date', 'due_date', 'sprint_start_date', 'sprint_end_date', mode='before')
    @classmethod
    def _empty_datetime_to_none(cls, v):
        if v == '' or v is None:
            return None
        return v


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    task_type: Optional[TaskType] = None
    assignee_id: Optional[str] = None
    created_by_id: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    # Sprint
    sprint_name: Optional[str] = None
    sprint_start_date: Optional[datetime] = None
    sprint_end_date: Optional[datetime] = None
    sprint_goal: Optional[str] = None
    # Estimates
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    story_points: Optional[int] = None
    labels: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    visible_to_customer: Optional[bool] = None

    # Coerce empty strings to None for optional datetime fields
    @field_validator('start_date', 'due_date', 'sprint_start_date', 'sprint_end_date', mode='before')
    @classmethod
    def _empty_datetime_to_none_update(cls, v):
        if v == '' or v is None:
            return None
        return v


class Task(TaskBase):
    id: str
    project_id: str
    assignee_id: Optional[str] = None
    created_by_id: str
    parent_task_id: Optional[str] = None
    # Recurrence linkage (template -> generated task)
    recurring_template_id: Optional[str] = None
    position: int = 0
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    # Sprint
    sprint_name: Optional[str] = None
    sprint_start_date: Optional[datetime] = None
    sprint_end_date: Optional[datetime] = None
    sprint_goal: Optional[str] = None
    # Estimates
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
    visible_to_customer: bool = False
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
