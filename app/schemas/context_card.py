from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from ..models.context_card import ContextType


class ContextCardBase(BaseModel):
    title: str
    content: str
    context_type: ContextType
    task_id: Optional[str] = None
    tags: Optional[List[str]] = []
    impact_level: Optional[str] = "medium"
    confidence_level: Optional[str] = "medium"
    linked_decisions: Optional[List[str]] = []
    linked_tasks: Optional[List[str]] = []
    linked_documents: Optional[List[str]] = []
    trigger_event: Optional[str] = None


class ContextCardCreate(ContextCardBase):
    project_id: str


class ContextCardUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    context_type: Optional[ContextType] = None
    tags: Optional[List[str]] = None
    impact_level: Optional[str] = None
    confidence_level: Optional[str] = None
    linked_decisions: Optional[List[str]] = None
    linked_tasks: Optional[List[str]] = None
    linked_documents: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_archived: Optional[bool] = None


class ContextCard(ContextCardBase):
    id: str
    project_id: str
    created_by_id: str
    auto_captured: bool
    is_active: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContextCardResponse(ContextCard):
    """Response model with additional computed fields"""
    created_by_name: Optional[str] = None
    project_name: Optional[str] = None
    task_title: Optional[str] = None
    
    class Config:
        from_attributes = True





