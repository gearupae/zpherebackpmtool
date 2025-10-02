from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


class ProjectCommentAttachmentBase(BaseModel):
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    mime_type: Optional[str] = None


class ProjectCommentAttachment(ProjectCommentAttachmentBase):
    id: str
    comment_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProjectCommentBase(BaseModel):
    content: str
    parent_comment_id: Optional[str] = None
    mentions: Optional[List[str]] = []
    linked_tasks: Optional[List[str]] = []


class ProjectCommentCreate(ProjectCommentBase):
    attachment_ids: Optional[List[str]] = []  # List of uploaded file IDs to attach


class ProjectCommentUpdate(BaseModel):
    content: Optional[str] = None
    mentions: Optional[List[str]] = None
    linked_tasks: Optional[List[str]] = None
    is_edited: Optional[bool] = None
    is_deleted: Optional[bool] = None


class UserInfo(BaseModel):
    id: str
    username: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: Optional[str]
    avatar_url: Optional[str]
    
    class Config:
        from_attributes = True


class ProjectComment(ProjectCommentBase):
    id: str
    project_id: str
    user_id: str
    is_edited: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    user: Optional[UserInfo] = None
    attachments: Optional[List[ProjectCommentAttachment]] = []
    # replies: Optional[List["ProjectComment"]] = []  # Removed to avoid lazy loading issues
    
    class Config:
        from_attributes = True

class ProjectCommentResponse(ProjectCommentBase):
    id: str
    project_id: str
    user_id: str
    is_edited: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    user: Optional[UserInfo] = None
    attachments: Optional[List[ProjectCommentAttachment]] = []
    
    class Config:
        from_attributes = True
        # Exclude the replies field to avoid lazy loading issues
        exclude = {"replies"}


# Update forward reference
ProjectComment.model_rebuild()
