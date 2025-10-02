from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class RecurringTaskTemplateBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"
    task_type: Optional[str] = "task"
    estimated_hours: Optional[int] = None
    story_points: Optional[int] = None
    default_assignee_id: Optional[str] = None
    frequency: str  # daily, weekly, monthly, quarterly, yearly, custom
    interval_value: Optional[int] = 1
    days_of_week: Optional[List[int]] = None  # [1,3,5] for Mon, Wed, Fri
    day_of_month: Optional[int] = None  # 15 for 15th of each month
    months_of_year: Optional[List[int]] = None  # [1,6] for Jan and June
    start_date: datetime
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None
    advance_creation_days: Optional[int] = 0
    skip_weekends: Optional[bool] = False
    skip_holidays: Optional[bool] = False
    custom_fields: Optional[Dict[str, Any]] = None
    labels: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class RecurringTaskTemplateCreate(RecurringTaskTemplateBase):
    project_id: str


class RecurringTaskTemplateUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    task_type: Optional[str] = None
    estimated_hours: Optional[int] = None
    story_points: Optional[int] = None
    default_assignee_id: Optional[str] = None
    frequency: Optional[str] = None
    interval_value: Optional[int] = None
    days_of_week: Optional[List[int]] = None
    day_of_month: Optional[int] = None
    months_of_year: Optional[List[int]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_occurrences: Optional[int] = None
    advance_creation_days: Optional[int] = None
    skip_weekends: Optional[bool] = None
    skip_holidays: Optional[bool] = None
    custom_fields: Optional[Dict[str, Any]] = None
    labels: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_paused: Optional[bool] = None


class RecurringTaskTemplateResponse(RecurringTaskTemplateBase):
    id: str
    project_id: str
    is_active: bool
    is_paused: bool
    last_generated_date: Optional[datetime] = None
    next_due_date: Optional[datetime] = None
    total_generated: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
