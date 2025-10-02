from sqlalchemy import Column, String, Text, ForeignKey, JSON, Boolean, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship
from enum import Enum
from .base import UUIDBaseModel


class ContextType(str, Enum):
    DECISION = "DECISION"
    DISCUSSION = "DISCUSSION"
    INSIGHT = "INSIGHT"
    LEARNING = "LEARNING"
    ISSUE = "ISSUE"
    SOLUTION = "SOLUTION"


class ContextCard(UUIDBaseModel):
    """Context card model for capturing WHY behind decisions"""
    __tablename__ = "context_cards"

    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    decision_rationale = Column(Text)  # WHY behind the decision
    impact_assessment = Column(Text)  # Expected impact and consequences
    context_type = Column(SQLEnum(ContextType), nullable=False, default=ContextType.DECISION)
    priority = Column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Relationships
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Context metadata
    tags = Column(JSON, default=list)  # List of tags for categorization
    impact_level = Column(String(20), default="medium")  # low, medium, high, critical
    confidence_level = Column(String(20), default="medium")  # low, medium, high
    
    # Linking to other entities
    linked_tasks = Column(JSON, default=list)  # List of task IDs
    linked_projects = Column(JSON, default=list)  # List of project IDs  
    linked_discussions = Column(JSON, default=list)  # List of discussion/comment IDs
    
    # Enhanced auto-capture functionality
    auto_captured = Column(Boolean, default=False)
    capture_source = Column(String(100))  # Source that triggered auto-capture
    trigger_event = Column(String(100))  # What event triggered the capture
    extraction_keywords = Column(JSON, default=list)  # Keywords that triggered extraction
    sentiment_score = Column(Float)  # Sentiment analysis score (-1 to 1)
    decision_indicators = Column(JSON, default=list)  # Phrases indicating decisions
    auto_review_needed = Column(Boolean, default=True)  # Whether human review is needed
    confidence_score = Column(Float, default=0.5)  # Auto-capture confidence (0-1)
    
    # Status and visibility
    is_active = Column(Boolean, default=True)
    is_archived = Column(Boolean, default=False)
    
    # Relationships
    project = relationship("Project", back_populates="context_cards")
    task = relationship("Task", back_populates="context_cards")
    created_by = relationship("User")

    def __repr__(self):
        return f"<ContextCard(title='{self.title}', type='{self.context_type}')>"




