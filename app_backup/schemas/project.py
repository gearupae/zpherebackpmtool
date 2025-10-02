from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime
from ..models.project import ProjectStatus, ProjectPriority


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.PLANNING
    priority: ProjectPriority = ProjectPriority.MEDIUM


class ProjectCreate(ProjectBase):
    slug: Optional[str] = None  # Will be auto-generated if not provided
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    budget: Optional[int] = None
    hourly_rate: Optional[int] = None
    estimated_hours: Optional[int] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    budget: Optional[int] = None
    hourly_rate: Optional[int] = None
    estimated_hours: Optional[int] = None
    settings: Optional[Dict[str, Any]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class Project(ProjectBase):
    id: str
    slug: str
    organization_id: str
    owner_id: str
    client_id: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    budget: Optional[int] = None
    hourly_rate: Optional[int] = None
    estimated_hours: Optional[int] = None
    actual_hours: int = 0
    settings: Dict[str, Any] = {}
    custom_fields: Dict[str, Any] = {}
    is_template: bool = False
    is_archived: bool = False
    is_public: bool = False
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
