from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class WorkspaceBase(BaseModel):
    name: str
    description: Optional[str] = None
    slug: Optional[str] = None
    color: Optional[str] = "#3B82F6"
    icon: Optional[str] = "folder"
    is_private: Optional[bool] = False
    settings: Optional[Dict[str, Any]] = None


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_private: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None


class WorkspaceResponse(WorkspaceBase):
    id: str
    organization_id: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkspaceMemberBase(BaseModel):
    user_id: str
    role: str = "member"
    can_create_projects: Optional[bool] = True
    can_invite_users: Optional[bool] = False
    can_manage_workspace: Optional[bool] = False


class WorkspaceMemberCreate(WorkspaceMemberBase):
    pass


class WorkspaceMemberUpdate(BaseModel):
    role: Optional[str] = None
    can_create_projects: Optional[bool] = None
    can_invite_users: Optional[bool] = None
    can_manage_workspace: Optional[bool] = None


class WorkspaceMemberResponse(WorkspaceMemberBase):
    id: str
    workspace_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
