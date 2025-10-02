"""Scope and Change Management Models"""
import enum
from sqlalchemy import Column, String, Text, JSON, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import UUIDBaseModel


class ChangeRequestStatus(str, enum.Enum):
    """Change request status types"""
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    CANCELLED = "cancelled"


class ChangeRequestPriority(str, enum.Enum):
    """Change request priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeRequestType(str, enum.Enum):
    """Types of change requests"""
    SCOPE_ADDITION = "scope_addition"
    SCOPE_MODIFICATION = "scope_modification"
    SCOPE_REMOVAL = "scope_removal"
    REQUIREMENT_CHANGE = "requirement_change"
    TECHNICAL_CHANGE = "technical_change"
    RESOURCE_CHANGE = "resource_change"
    TIMELINE_CHANGE = "timeline_change"
    BUDGET_CHANGE = "budget_change"


class ImpactLevel(str, enum.Enum):
    """Impact assessment levels"""
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProjectScope(UUIDBaseModel):
    """Project scope tracking and management"""
    __tablename__ = "project_scopes"
    
    # Project relationship
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    # Scope definition
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    scope_type = Column(String(50), default="feature")  # feature, deliverable, milestone, requirement
    
    # Scope details
    original_description = Column(Text)  # Original scope definition
    current_description = Column(Text)  # Current scope definition
    acceptance_criteria = Column(JSON, default=list)  # List of acceptance criteria
    
    # Status and tracking
    is_original_scope = Column(Boolean, default=True)  # Was this in original scope?
    is_active = Column(Boolean, default=True)
    is_completed = Column(Boolean, default=False)
    completion_date = Column(DateTime(timezone=True))
    
    # Estimates and tracking
    original_effort_estimate = Column(Float)  # Original effort estimate in hours
    current_effort_estimate = Column(Float)  # Current effort estimate
    actual_effort = Column(Float, default=0.0)  # Actual effort spent
    
    # Dependencies and relationships
    parent_scope_id = Column(String, ForeignKey("project_scopes.id"))
    dependencies = Column(JSON, default=list)  # List of dependent scope IDs
    
    # Change tracking
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    last_modified_by_id = Column(String, ForeignKey("users.id"))
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    project = relationship("Project")
    created_by = relationship("User", foreign_keys=[created_by_id])
    last_modified_by = relationship("User", foreign_keys=[last_modified_by_id])
    parent_scope = relationship("ProjectScope", remote_side="ProjectScope.id")
    change_requests = relationship("ChangeRequest", back_populates="related_scope")
    
    def __repr__(self):
        return f"<ProjectScope(name='{self.name}', project_id='{self.project_id}')>"


class ChangeRequest(UUIDBaseModel):
    """Change requests for project scope modifications"""
    __tablename__ = "change_requests"
    
    # Request metadata
    request_number = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Project and scope relationships
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    related_scope_id = Column(String, ForeignKey("project_scopes.id"))
    
    # Request details
    change_type = Column(SQLEnum(ChangeRequestType), nullable=False)
    priority = Column(SQLEnum(ChangeRequestPriority), default=ChangeRequestPriority.MEDIUM)
    status = Column(SQLEnum(ChangeRequestStatus), default=ChangeRequestStatus.PROPOSED)
    
    # Requestor and stakeholders
    requested_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    assigned_to_id = Column(String, ForeignKey("users.id"))  # Who is reviewing/implementing
    stakeholders = Column(JSON, default=list)  # List of stakeholder user IDs
    
    # Business justification
    business_justification = Column(Text)
    expected_benefits = Column(JSON, default=list)
    risk_assessment = Column(Text)
    
    # Impact assessment
    time_impact_hours = Column(Float)  # Estimated time impact
    cost_impact = Column(Integer)  # Cost impact in cents
    resource_impact = Column(JSON, default=dict)  # Resource requirements
    timeline_impact_days = Column(Integer)  # Timeline impact in days
    overall_impact = Column(SQLEnum(ImpactLevel), default=ImpactLevel.MEDIUM)
    
    # Technical details
    technical_requirements = Column(JSON, default=list)
    implementation_approach = Column(Text)
    testing_requirements = Column(JSON, default=list)
    
    # Approval workflow
    approval_required = Column(Boolean, default=True)
    approvers = Column(JSON, default=list)  # List of required approver user IDs
    approved_by = Column(JSON, default=list)  # List of users who approved
    rejected_by = Column(JSON, default=list)  # List of users who rejected
    
    # Dates and timeline
    requested_date = Column(DateTime(timezone=True), server_default=func.now())
    required_by_date = Column(DateTime(timezone=True))
    reviewed_date = Column(DateTime(timezone=True))
    approved_date = Column(DateTime(timezone=True))
    implemented_date = Column(DateTime(timezone=True))
    
    # Implementation tracking
    implementation_tasks = Column(JSON, default=list)  # Related task IDs
    implementation_notes = Column(Text)
    actual_time_spent = Column(Float)  # Actual implementation time
    actual_cost = Column(Integer)  # Actual cost in cents
    
    # Documentation and attachments
    supporting_documents = Column(JSON, default=list)  # Document references
    comments = Column(JSON, default=list)  # Change request comments
    
    # Relationships
    project = relationship("Project")
    related_scope = relationship("ProjectScope", back_populates="change_requests")
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    
    def __repr__(self):
        return f"<ChangeRequest(number='{self.request_number}', status='{self.status}')>"


class ScopeTimeline(UUIDBaseModel):
    """Timeline tracking for scope changes"""
    __tablename__ = "scope_timelines"
    
    # Project relationship
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    # Timeline entry details
    event_type = Column(String(50), nullable=False)  # scope_added, scope_modified, scope_removed, etc.
    event_description = Column(String(500), nullable=False)
    
    # Related entities
    related_scope_id = Column(String, ForeignKey("project_scopes.id"))
    related_change_request_id = Column(String, ForeignKey("change_requests.id"))
    
    # Event metadata
    event_date = Column(DateTime(timezone=True), server_default=func.now())
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Impact tracking
    impact_summary = Column(JSON, default=dict)  # Summary of impact metrics
    
    # Snapshot data
    scope_snapshot = Column(JSON, default=dict)  # Snapshot of scope at this point
    project_snapshot = Column(JSON, default=dict)  # Snapshot of project metrics
    
    # Relationships
    project = relationship("Project")
    related_scope = relationship("ProjectScope")
    related_change_request = relationship("ChangeRequest")
    created_by = relationship("User")
    
    def __repr__(self):
        return f"<ScopeTimeline(project_id='{self.project_id}', event='{self.event_type}')>"


class ScopeBaseline(UUIDBaseModel):
    """Project scope baselines for comparison"""
    __tablename__ = "scope_baselines"
    
    # Project relationship
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    # Baseline metadata
    name = Column(String(255), nullable=False)
    description = Column(Text)
    baseline_type = Column(String(50), default="approved")  # original, approved, current
    
    # Baseline content
    scope_items = Column(JSON, nullable=False)  # Complete scope definition
    estimated_effort = Column(Float)  # Total estimated effort
    estimated_cost = Column(Integer)  # Total estimated cost
    estimated_duration_days = Column(Integer)  # Estimated duration
    
    # Baseline status
    is_active = Column(Boolean, default=True)
    is_approved = Column(Boolean, default=False)
    approved_by_id = Column(String, ForeignKey("users.id"))
    approved_date = Column(DateTime(timezone=True))
    
    # Creation tracking
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    baseline_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    project = relationship("Project")
    created_by = relationship("User", foreign_keys=[created_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    
    def __repr__(self):
        return f"<ScopeBaseline(name='{self.name}', project_id='{self.project_id}')>"
