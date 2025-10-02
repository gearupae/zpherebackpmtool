"""Scope and Change Management Schemas"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from ..models.scope_management import ChangeRequestStatus, ChangeRequestPriority, ChangeRequestType, ImpactLevel


class ProjectScopeBase(BaseModel):
    """Base project scope schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    scope_type: str = Field(default="feature", pattern="^(feature|deliverable|milestone|requirement)$")
    original_effort_estimate: Optional[float] = Field(None, ge=0)
    current_effort_estimate: Optional[float] = Field(None, ge=0)


class ProjectScopeCreate(ProjectScopeBase):
    """Create project scope schema"""
    project_id: str
    original_description: Optional[str] = None
    acceptance_criteria: List[str] = []
    parent_scope_id: Optional[str] = None
    dependencies: List[str] = []


class ProjectScopeUpdate(BaseModel):
    """Update project scope schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    current_description: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None
    current_effort_estimate: Optional[float] = Field(None, ge=0)
    actual_effort: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None
    is_completed: Optional[bool] = None
    completion_date: Optional[datetime] = None
    dependencies: Optional[List[str]] = None


class ProjectScope(ProjectScopeBase):
    """Project scope schema with all fields"""
    id: str
    project_id: str
    original_description: Optional[str]
    current_description: Optional[str]
    acceptance_criteria: List[str]
    is_original_scope: bool
    is_active: bool
    is_completed: bool
    completion_date: Optional[datetime]
    actual_effort: float
    parent_scope_id: Optional[str]
    dependencies: List[str]
    created_by_id: str
    last_modified_by_id: Optional[str]
    last_modified_date: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ChangeRequestBase(BaseModel):
    """Base change request schema"""
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    change_type: ChangeRequestType
    priority: ChangeRequestPriority = ChangeRequestPriority.MEDIUM
    business_justification: Optional[str] = None
    risk_assessment: Optional[str] = None


class ChangeRequestCreate(ChangeRequestBase):
    """Create change request schema"""
    project_id: str
    related_scope_id: Optional[str] = None
    expected_benefits: List[str] = []
    time_impact_hours: Optional[float] = Field(None, ge=0)
    cost_impact: Optional[int] = None  # in cents
    resource_impact: Dict[str, Any] = {}
    timeline_impact_days: Optional[int] = None
    overall_impact: ImpactLevel = ImpactLevel.MEDIUM
    technical_requirements: List[str] = []
    implementation_approach: Optional[str] = None
    testing_requirements: List[str] = []
    approval_required: bool = True
    approvers: List[str] = []
    required_by_date: Optional[datetime] = None
    supporting_documents: List[str] = []


class ChangeRequestUpdate(BaseModel):
    """Update change request schema"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[ChangeRequestStatus] = None
    priority: Optional[ChangeRequestPriority] = None
    assigned_to_id: Optional[str] = None
    business_justification: Optional[str] = None
    risk_assessment: Optional[str] = None
    expected_benefits: Optional[List[str]] = None
    time_impact_hours: Optional[float] = Field(None, ge=0)
    cost_impact: Optional[int] = None
    resource_impact: Optional[Dict[str, Any]] = None
    timeline_impact_days: Optional[int] = None
    overall_impact: Optional[ImpactLevel] = None
    technical_requirements: Optional[List[str]] = None
    implementation_approach: Optional[str] = None
    testing_requirements: Optional[List[str]] = None
    approval_required: Optional[bool] = None
    approvers: Optional[List[str]] = None
    approved_by: Optional[List[str]] = None
    rejected_by: Optional[List[str]] = None
    required_by_date: Optional[datetime] = None
    reviewed_date: Optional[datetime] = None
    approved_date: Optional[datetime] = None
    implemented_date: Optional[datetime] = None
    implementation_tasks: Optional[List[str]] = None
    implementation_notes: Optional[str] = None
    actual_time_spent: Optional[float] = Field(None, ge=0)
    actual_cost: Optional[int] = None
    supporting_documents: Optional[List[str]] = None
    comments: Optional[List[Dict[str, Any]]] = None


class ChangeRequest(ChangeRequestBase):
    """Change request schema with all fields"""
    id: str
    request_number: str
    project_id: str
    related_scope_id: Optional[str]
    status: ChangeRequestStatus
    requested_by_id: str
    assigned_to_id: Optional[str]
    stakeholders: List[str]
    expected_benefits: List[str]
    time_impact_hours: Optional[float]
    cost_impact: Optional[int]
    resource_impact: Dict[str, Any]
    timeline_impact_days: Optional[int]
    overall_impact: ImpactLevel
    technical_requirements: List[str]
    implementation_approach: Optional[str]
    testing_requirements: List[str]
    approval_required: bool
    approvers: List[str]
    approved_by: List[str]
    rejected_by: List[str]
    requested_date: datetime
    required_by_date: Optional[datetime]
    reviewed_date: Optional[datetime]
    approved_date: Optional[datetime]
    implemented_date: Optional[datetime]
    implementation_tasks: List[str]
    implementation_notes: Optional[str]
    actual_time_spent: Optional[float]
    actual_cost: Optional[int]
    supporting_documents: List[str]
    comments: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ScopeTimelineBase(BaseModel):
    """Base scope timeline schema"""
    event_type: str = Field(..., min_length=1, max_length=50)
    event_description: str = Field(..., min_length=1, max_length=500)
    event_date: datetime


class ScopeTimelineCreate(ScopeTimelineBase):
    """Create scope timeline schema"""
    project_id: str
    related_scope_id: Optional[str] = None
    related_change_request_id: Optional[str] = None
    impact_summary: Dict[str, Any] = {}
    scope_snapshot: Dict[str, Any] = {}
    project_snapshot: Dict[str, Any] = {}


class ScopeTimeline(ScopeTimelineBase):
    """Scope timeline schema with all fields"""
    id: str
    project_id: str
    related_scope_id: Optional[str]
    related_change_request_id: Optional[str]
    created_by_id: str
    impact_summary: Dict[str, Any]
    scope_snapshot: Dict[str, Any]
    project_snapshot: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ScopeBaselineBase(BaseModel):
    """Base scope baseline schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    baseline_type: str = Field(default="approved", pattern="^(original|approved|current)$")
    estimated_effort: Optional[float] = Field(None, ge=0)
    estimated_cost: Optional[int] = None  # in cents
    estimated_duration_days: Optional[int] = Field(None, ge=1)


class ScopeBaselineCreate(ScopeBaselineBase):
    """Create scope baseline schema"""
    project_id: str
    scope_items: Dict[str, Any] = {}
    is_approved: bool = False


class ScopeBaselineUpdate(BaseModel):
    """Update scope baseline schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    scope_items: Optional[Dict[str, Any]] = None
    estimated_effort: Optional[float] = Field(None, ge=0)
    estimated_cost: Optional[int] = None
    estimated_duration_days: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    is_approved: Optional[bool] = None
    approved_by_id: Optional[str] = None
    approved_date: Optional[datetime] = None


class ScopeBaseline(ScopeBaselineBase):
    """Scope baseline schema with all fields"""
    id: str
    project_id: str
    scope_items: Dict[str, Any]
    is_active: bool
    is_approved: bool
    approved_by_id: Optional[str]
    approved_date: Optional[datetime]
    created_by_id: str
    baseline_date: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Summary and analysis schemas
class ScopeAnalysis(BaseModel):
    """Scope analysis summary"""
    project_id: str
    total_scope_items: int
    completed_scope_items: int
    completion_percentage: float
    original_scope_count: int
    added_scope_count: int
    removed_scope_count: int
    scope_change_percentage: float
    total_estimated_effort: float
    total_actual_effort: float
    effort_variance_percentage: float
    scope_health_status: str


class ChangeRequestSummary(BaseModel):
    """Change request summary"""
    project_id: str
    total_change_requests: int
    pending_requests: int
    approved_requests: int
    rejected_requests: int
    implemented_requests: int
    total_time_impact: float
    total_cost_impact: int
    avg_approval_time_days: float


class ScopeVisualData(BaseModel):
    """Data for scope visualization"""
    original_scope: List[Dict[str, Any]]
    current_scope: List[Dict[str, Any]]
    scope_changes: List[Dict[str, Any]]
    timeline_events: List[Dict[str, Any]]
    baseline_comparison: Dict[str, Any]


class ImpactAssessment(BaseModel):
    """Impact assessment result"""
    change_request_id: str
    overall_impact: ImpactLevel
    time_impact_hours: float
    cost_impact: int
    resource_impact: Dict[str, Any]
    timeline_impact_days: int
    risk_factors: List[str]
    mitigation_strategies: List[str]
    confidence_percentage: float
