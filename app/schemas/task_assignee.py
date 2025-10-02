from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class TaskAssigneeBase(BaseModel):
    user_id: str
    is_primary: Optional[bool] = False


class TaskAssigneeCreate(TaskAssigneeBase):
    pass


class TaskAssigneeUpdate(BaseModel):
    is_primary: Optional[bool] = None


class UserInfo(BaseModel):
    id: str
    username: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: Optional[str]
    avatar_url: Optional[str]
    
    class Config:
        from_attributes = True


class TaskAssignee(TaskAssigneeBase):
    id: str
    task_id: str
    assigned_at: Optional[datetime]
    assigned_by_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    user: Optional[UserInfo] = None
    assigned_by: Optional[UserInfo] = None
    
    class Config:
        from_attributes = True
