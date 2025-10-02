from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


class CustomerAttachment(BaseModel):
    id: str
    customer_id: str
    organization_id: Optional[str] = None
    original_filename: Optional[str] = None
    content_type: Optional[str] = None
    size: Optional[int] = None
    storage_path: Optional[str] = None
    uploaded_by: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    uploaded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerAttachmentList(BaseModel):
    attachments: List[CustomerAttachment]
