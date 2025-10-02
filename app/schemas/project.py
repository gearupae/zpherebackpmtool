from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime
from ..models.project import ProjectStatus, ProjectPriority, ProjectMemberRole


class ProjectMemberUser(BaseModel):
    id: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    username: Optional[str] = None

    class Config:
        from_attributes = True


class ProjectMemberIn(BaseModel):
    user_id: str
    role: Optional[ProjectMemberRole] = ProjectMemberRole.MEMBER
    can_edit_project: Optional[bool] = False
    can_create_tasks: Optional[bool] = True
    can_assign_tasks: Optional[bool] = False
    can_delete_tasks: Optional[bool] = False


class ProjectMemberOut(BaseModel):
    id: str
    user_id: str
    role: ProjectMemberRole
    can_edit_project: bool
    can_create_tasks: bool
    can_assign_tasks: bool
    can_delete_tasks: bool
    user: Optional[ProjectMemberUser] = None

    class Config:
        from_attributes = True


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.PLANNING
    priority: ProjectPriority = ProjectPriority.MEDIUM


class ProjectCreate(ProjectBase):
    slug: Optional[str] = None  # Will be auto-generated if not provided
    customer_id: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    budget: Optional[int] = None
    hourly_rate: Optional[int] = None
    estimated_hours: Optional[int] = None
    members: Optional[List[ProjectMemberIn]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    customer_id: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    budget: Optional[int] = None
    hourly_rate: Optional[int] = None
    estimated_hours: Optional[int] = None
    settings: Optional[Dict[str, Any]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    members: Optional[List[ProjectMemberIn]] = None


class Project(ProjectBase):
    id: str
    slug: str
    organization_id: str
    owner_id: str
    customer_id: Optional[str] = None
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
    members: List[ProjectMemberOut] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
