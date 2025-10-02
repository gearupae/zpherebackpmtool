from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
import enum
from .base import UUIDBaseModel


class MilestoneStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"
    CANCELLED = "cancelled"


class Milestone(UUIDBaseModel):
    """Project milestone model for tracking key checkpoints"""
    __tablename__ = "milestones"
    
    # Basic milestone info
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Project relationship
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    # Milestone details
    status = Column(String(50), default="upcoming")  # upcoming, in_progress, completed, missed, cancelled
    
    # Dates
    due_date = Column(DateTime(timezone=True), nullable=False)
    completed_date = Column(DateTime(timezone=True))
    
    # Progress tracking
    completion_criteria = Column(JSON, default=list)  # List of criteria that need to be met
    associated_tasks = Column(JSON, default=list)  # Task IDs associated with this milestone
    
    # Metadata
    color = Column(String(7), default="#8B5CF6")  # Hex color for milestone
    icon = Column(String(50), default="flag")  # Icon name
    
    # Flags
    is_critical = Column(Boolean, default=False)  # Critical path milestone
    
    # Relationships
    project = relationship("Project", back_populates="milestones")
    
    @property
    def is_overdue(self):
        if self.status in ["completed", "cancelled"]:
            return False
        from datetime import datetime
        return datetime.utcnow() > self.due_date
    
    @property
    def completion_percentage(self):
        if not self.completion_criteria:
            return 100 if self.status == "completed" else 0
        
        # Calculate based on completion criteria
        # This could be enhanced with more sophisticated logic
        if self.status == "completed":
            return 100
        elif self.status == "in_progress":
            return 50  # Could be calculated based on associated tasks
        else:
            return 0
    
    def __repr__(self):
        return f"<Milestone(name='{self.name}', project_id='{self.project_id}', status='{self.status}')>"
