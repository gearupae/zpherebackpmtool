from sqlalchemy import Column, String, Text, ForeignKey, JSON, Boolean, DateTime, Enum as SQLEnum, Integer
from sqlalchemy.orm import relationship
from enum import Enum
from datetime import datetime
from .base import UUIDBaseModel


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    SUPERSEDED = "superseded"


class DecisionImpact(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionCategory(str, Enum):
    TECHNICAL = "technical"
    ARCHITECTURAL = "architectural"
    BUSINESS = "business"
    PROCESS = "process"
    RESOURCE = "resource"
    TIMELINE = "timeline"
    QUALITY = "quality"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class DecisionLog(UUIDBaseModel):
    """Decision log model for tracking key project decisions"""
    __tablename__ = "decision_logs"

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Decision metadata
    decision_number = Column(Integer, autoincrement=True, unique=True)
    status = Column(SQLEnum(DecisionStatus), default=DecisionStatus.PROPOSED)
    category = Column(SQLEnum(DecisionCategory), nullable=False)
    impact_level = Column(SQLEnum(DecisionImpact), default=DecisionImpact.MEDIUM)
    
    # Context and rationale
    problem_statement = Column(Text, nullable=False)  # What problem does this solve
    rationale = Column(Text, nullable=False)  # Why this decision was made
    alternatives_considered = Column(JSON, default=list)  # Other options considered
    assumptions = Column(JSON, default=list)  # Underlying assumptions
    constraints = Column(JSON, default=list)  # Limiting factors
    
    # Decision outcome
    decision_outcome = Column(Text)  # What was decided
    success_criteria = Column(JSON, default=list)  # How to measure success
    risks = Column(JSON, default=list)  # Associated risks
    mitigation_strategies = Column(JSON, default=list)  # Risk mitigation
    
    # Stakeholders and approval
    decision_maker_id = Column(String, ForeignKey("users.id"), nullable=False)
    stakeholders = Column(JSON, default=list)  # List of stakeholder user IDs
    approvers = Column(JSON, default=list)  # List of approver user IDs
    
    # Related entities
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    related_tasks = Column(JSON, default=list)  # List of related task IDs
    related_decisions = Column(JSON, default=list)  # List of related decision IDs
    
    # Implementation tracking
    implementation_date = Column(DateTime)
    implementation_notes = Column(Text)
    review_date = Column(DateTime)  # When to review this decision
    
    # Documentation and evidence
    supporting_documents = Column(JSON, default=list)  # Document references
    evidence = Column(JSON, default=list)  # Supporting evidence
    communication_plan = Column(JSON, default=list)  # How decision was communicated
    
    # Timeline
    decision_date = Column(DateTime, default=datetime.utcnow)
    effective_date = Column(DateTime)  # When decision takes effect
    expiry_date = Column(DateTime)  # When decision expires (if applicable)
    
    # Tracking and follow-up
    follow_up_actions = Column(JSON, default=list)  # Actions resulting from decision
    lessons_learned = Column(Text)  # What was learned from this decision
    
    # Relationships
    project = relationship("Project", back_populates="decision_logs")
    decision_maker = relationship("User")

    def __repr__(self):
        return f"<DecisionLog(#{self.decision_number}: '{self.title}', status='{self.status}')>"





