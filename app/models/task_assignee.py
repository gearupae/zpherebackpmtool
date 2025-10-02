from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from .base import UUIDBaseModel


class TaskAssignee(UUIDBaseModel):
    """Task assignee model for multiple assignees per task"""
    __tablename__ = "task_assignees"
    
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Assignment details
    is_primary = Column(Boolean, default=False)  # Primary assignee
    assigned_at = Column(DateTime(timezone=True))
    assigned_by_id = Column(String, ForeignKey("users.id"))
    
    # Relationships
    task = relationship("Task", back_populates="assignees")
    user = relationship("User", foreign_keys=[user_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])
    
    def __repr__(self):
        return f"<TaskAssignee(task_id='{self.task_id}', user_id='{self.user_id}', is_primary='{self.is_primary}')>"
