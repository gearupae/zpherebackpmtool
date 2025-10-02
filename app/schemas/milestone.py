from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class MilestoneBase(BaseModel):
    name: str
    description: Optional[str] = None
    due_date: datetime
    completion_criteria: Optional[List[str]] = None
    associated_tasks: Optional[List[str]] = None
    color: Optional[str] = "#8B5CF6"
    icon: Optional[str] = "flag"
    is_critical: Optional[bool] = False


class MilestoneCreate(MilestoneBase):
    project_id: str


class MilestoneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    completion_criteria: Optional[List[str]] = None
    associated_tasks: Optional[List[str]] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_critical: Optional[bool] = None
    status: Optional[str] = None


class MilestoneResponse(MilestoneBase):
    id: str
    project_id: str
    status: str
    completed_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # Computed properties
    is_overdue: bool
    completion_percentage: int

    class Config:
        from_attributes = True
