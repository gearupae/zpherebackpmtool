from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator
from datetime import datetime
from ..models.proposal import ProposalStatus, ProposalType


class ProposalBase(BaseModel):
    """Base proposal schema"""
    title: str
    description: Optional[str] = None
    proposal_type: ProposalType = ProposalType.PROJECT
    content: Dict[str, Any] = {}
    template_id: Optional[str] = None
    custom_template: Dict[str, Any] = {}
    total_amount: Optional[int] = None  # In cents
    currency: str = "usd"
    valid_until: Optional[datetime] = None
    notes: Optional[str] = None
    tags: List[str] = []
    custom_fields: Dict[str, Any] = {}


class ProposalCreate(ProposalBase):
    """Schema for creating a proposal"""
    customer_id: str


class ProposalUpdate(BaseModel):
    """Schema for updating a proposal"""
    title: Optional[str] = None
    description: Optional[str] = None
    proposal_type: Optional[ProposalType] = None
    content: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None
    custom_template: Optional[Dict[str, Any]] = None
    total_amount: Optional[int] = None
    currency: Optional[str] = None
    valid_until: Optional[datetime] = None
    status: Optional[ProposalStatus] = None
    response_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class Proposal(ProposalBase):
    """Proposal schema for responses"""
    id: str
    proposal_number: str
    organization_id: str
    customer_id: str
    created_by_id: str
    status: ProposalStatus
    sent_date: Optional[datetime] = None
    viewed_date: Optional[datetime] = None
    responded_date: Optional[datetime] = None
    response_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    is_template: bool
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    is_expired: bool
    status_color: str
    
    class Config:
        from_attributes = True


class ProposalList(BaseModel):
    """Schema for proposal list responses"""
    items: List[Proposal]
    total: int
    page: int
    size: int
    pages: int


class ProposalTemplateBase(BaseModel):
    """Base proposal template schema"""
    name: str
    description: Optional[str] = None
    is_default: bool = False
    sections: List[Dict[str, Any]] = []
    styling: Dict[str, Any] = {}
    variables: List[str] = []


class ProposalTemplateCreate(ProposalTemplateBase):
    """Schema for creating a proposal template"""
    pass


class ProposalTemplateUpdate(BaseModel):
    """Schema for updating a proposal template"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None
    sections: Optional[List[Dict[str, Any]]] = None
    styling: Optional[Dict[str, Any]] = None
    variables: Optional[List[str]] = None


class ProposalTemplate(ProposalTemplateBase):
    """Proposal template schema for responses"""
    id: str
    organization_id: str
    usage_count: int
    last_used: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProposalStats(BaseModel):
    """Proposal statistics"""
    total_proposals: int
    draft_proposals: int
    sent_proposals: int
    viewed_proposals: int
    accepted_proposals: int
    rejected_proposals: int
    expired_proposals: int
    total_value: int  # In cents
    conversion_rate: float  # Percentage
