from typing import Optional, List
from pydantic import BaseModel, EmailStr
from datetime import datetime
from ..models.user import UserRole, UserStatus
from ..models.project import ProjectMemberRole


class TeamMemberBase(BaseModel):
    email: EmailStr
    username: str
    first_name: str
    last_name: str
    role: Optional[UserRole] = UserRole.MEMBER
    status: Optional[UserStatus] = UserStatus.PENDING
    timezone: Optional[str] = "UTC"
    phone: Optional[str] = None
    bio: Optional[str] = None
    address: Optional[str] = None


class TeamMemberCreate(TeamMemberBase):
    password: str


class TeamMemberUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    timezone: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


class TeamMember(TeamMemberBase):
    id: str
    full_name: str
    is_active: bool
    avatar_url: Optional[str] = None
    last_login: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProjectMemberBase(BaseModel):
    role: ProjectMemberRole = ProjectMemberRole.MEMBER
    can_edit_project: bool = False
    can_create_tasks: bool = True
    can_assign_tasks: bool = False
    can_delete_tasks: bool = False


class ProjectMemberCreate(ProjectMemberBase):
    user_id: str


class ProjectMemberUpdate(BaseModel):
    role: Optional[ProjectMemberRole] = None
    can_edit_project: Optional[bool] = None
    can_create_tasks: Optional[bool] = None
    can_assign_tasks: Optional[bool] = None
    can_delete_tasks: Optional[bool] = None


class ProjectMemberResponse(ProjectMemberBase):
    id: str
    project_id: str
    user_id: str
    user: TeamMember
    created_at: datetime
    
    class Config:
        from_attributes = True


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: ProjectMemberRole = ProjectMemberRole.MEMBER
    message: Optional[str] = None


class TeamStats(BaseModel):
    total_members: int
    active_members: int
    pending_members: int
    admin_count: int
    tenant_count: int


class ProjectTeamStats(BaseModel):
    total_members: int
    owner_count: int
    admin_count: int
    member_count: int
    viewer_count: int
    can_edit_count: int
    can_create_tasks_count: int
    can_assign_tasks_count: int
