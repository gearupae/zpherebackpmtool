from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from ..models.handoff_summary import HandoffType, HandoffStatus


class HandoffSummaryBase(BaseModel):
    title: str
    description: Optional[str] = None
    handoff_type: HandoffType
    to_user_id: str
    task_id: Optional[str] = None
    context_summary: str
    key_decisions: Optional[List[str]] = []
    pending_actions: Optional[List[str]] = []
    important_notes: Optional[List[str]] = []
    resources: Optional[List[str]] = []
    skills_required: Optional[List[str]] = []
    domain_knowledge: Optional[List[str]] = []
    stakeholder_contacts: Optional[List[str]] = []
    target_completion_date: Optional[datetime] = None
    approval_required: Optional[bool] = False


class HandoffSummaryCreate(HandoffSummaryBase):
    project_id: str


class HandoffSummaryUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[HandoffStatus] = None
    context_summary: Optional[str] = None
    key_decisions: Optional[List[str]] = None
    pending_actions: Optional[List[str]] = None
    important_notes: Optional[List[str]] = None
    resources: Optional[List[str]] = None
    skills_required: Optional[List[str]] = None
    domain_knowledge: Optional[List[str]] = None
    stakeholder_contacts: Optional[List[str]] = None
    target_completion_date: Optional[datetime] = None
    actual_completion_date: Optional[datetime] = None
    approval_required: Optional[bool] = None


class HandoffSummary(HandoffSummaryBase):
    id: str
    project_id: str
    from_user_id: str
    status: HandoffStatus
    handoff_date: datetime
    actual_completion_date: Optional[datetime]
    auto_generated: bool
    generation_source: Optional[str]
    confidence_score: Optional[str]
    reviewed_by_id: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HandoffSummaryResponse(HandoffSummary):
    """Response model with additional computed fields"""
    from_user_name: Optional[str] = None
    to_user_name: Optional[str] = None
    project_name: Optional[str] = None
    task_title: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    
    class Config:
        from_attributes = True





