from sqlalchemy import Column, String, Text, ForeignKey, JSON, Boolean, DateTime, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship
from enum import Enum
from datetime import datetime
from .base import UUIDBaseModel


class HandoffType(str, Enum):
    PHASE_TRANSITION = "phase_transition"
    TEAM_HANDOVER = "team_handover"
    ROLE_CHANGE = "role_change"
    PROJECT_TRANSFER = "project_transfer"
    TASK_ASSIGNMENT = "task_assignment"


class HandoffStatus(str, Enum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    COMPLETED = "completed"
    REJECTED = "rejected"


class HandoffSummary(UUIDBaseModel):
    """Handoff summary model for automated context transfer"""
    __tablename__ = "handoff_summaries"

    title = Column(String(255), nullable=False)
    description = Column(Text)
    handoff_type = Column(SQLEnum(HandoffType), nullable=False)
    status = Column(SQLEnum(HandoffStatus), default=HandoffStatus.INITIATED)
    
    # Source and target
    from_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Related entities
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    
    # Handoff content
    context_summary = Column(Text, nullable=False)  # Auto-generated summary
    key_decisions = Column(JSON, default=list)  # List of decision references
    pending_actions = Column(JSON, default=list)  # List of pending tasks/actions
    important_notes = Column(JSON, default=list)  # Critical information
    resources = Column(JSON, default=list)  # Links to documents, tools, etc.
    
    # Knowledge transfer
    skills_required = Column(JSON, default=list)  # Skills needed for handoff
    domain_knowledge = Column(JSON, default=list)  # Domain-specific knowledge
    stakeholder_contacts = Column(JSON, default=list)  # Important contacts
    
    # Timing
    handoff_date = Column(DateTime, default=datetime.utcnow)
    target_completion_date = Column(DateTime)
    actual_completion_date = Column(DateTime)
    
    # Enhanced auto-generation metadata
    auto_generated = Column(Boolean, default=True)
    generation_source = Column(String(100))  # What triggered auto-generation
    confidence_score = Column(Float, default=0.5)  # Auto-generation confidence (0-1)
    
    # AI-powered features
    context_extraction_keywords = Column(JSON, default=list)  # Keywords used for context extraction
    sentiment_analysis = Column(JSON, default=dict)  # Sentiment scores for different aspects
    completeness_score = Column(Float, default=0.5)  # How complete the handoff is (0-1)
    risk_indicators = Column(JSON, default=list)  # Detected risks and blockers
    knowledge_gaps = Column(JSON, default=list)  # Identified knowledge gaps
    
    # Smart recommendations
    recommended_followups = Column(JSON, default=list)  # AI-recommended follow-up actions
    priority_items = Column(JSON, default=list)  # High-priority items requiring attention
    related_handoffs = Column(JSON, default=list)  # Related handoff summaries
    
    # Review and approval
    reviewed_by_id = Column(String, ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    approval_required = Column(Boolean, default=False)
    
    # Relationships
    project = relationship("Project", back_populates="handoff_summaries")
    task = relationship("Task", back_populates="handoff_summaries")
    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user = relationship("User", foreign_keys=[to_user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])

    def __repr__(self):
        return f"<HandoffSummary(title='{self.title}', type='{self.handoff_type}', status='{self.status}')>"




