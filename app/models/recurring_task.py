from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime, JSON, Integer
from sqlalchemy.orm import relationship
import enum
from datetime import datetime, timedelta
from .base import UUIDBaseModel


class RecurrenceFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class RecurringTaskTemplate(UUIDBaseModel):
    """Template for recurring tasks"""
    __tablename__ = "recurring_task_templates"
    
    # Basic template info
    title = Column(String(500), nullable=False)
    description = Column(Text)
    
    # Project relationship
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    # Task template details
    priority = Column(String(50), default="medium")  # low, medium, high, critical
    task_type = Column(String(50), default="task")  # task, bug, feature, etc.
    estimated_hours = Column(Integer)
    story_points = Column(Integer)
    
    # Assignment
    default_assignee_id = Column(String, ForeignKey("users.id"))
    
    # Recurrence settings
    frequency = Column(String(50), nullable=False)  # daily, weekly, monthly, quarterly, yearly, custom
    interval_value = Column(Integer, default=1)  # Every X days/weeks/months
    days_of_week = Column(JSON, default=list)  # For weekly: [1,3,5] for Mon, Wed, Fri
    day_of_month = Column(Integer)  # For monthly: 15 for 15th of each month
    months_of_year = Column(JSON, default=list)  # For yearly: [1,6] for Jan and June
    
    # Recurrence period
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True))  # When to stop creating tasks
    max_occurrences = Column(Integer)  # Alternative to end_date
    
    # Advanced settings
    advance_creation_days = Column(Integer, default=0)  # Create task X days before due
    skip_weekends = Column(Boolean, default=False)
    skip_holidays = Column(Boolean, default=False)
    
    # Metadata
    custom_fields = Column(JSON, default=dict)
    labels = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_paused = Column(Boolean, default=False)
    
    # Tracking
    last_generated_date = Column(DateTime(timezone=True))
    next_due_date = Column(DateTime(timezone=True))
    total_generated = Column(Integer, default=0)
    
    # Relationships
    project = relationship("Project", back_populates="recurring_templates")
    default_assignee = relationship("User", foreign_keys=[default_assignee_id])
    generated_tasks = relationship("Task", back_populates="recurring_template")
    
    def calculate_next_due_date(self, from_date=None):
        """Calculate the next due date based on recurrence settings"""
        if from_date is None:
            from_date = self.last_generated_date or self.start_date
        
        if self.frequency == RecurrenceFrequency.DAILY:
            return from_date + timedelta(days=self.interval_value)
        elif self.frequency == RecurrenceFrequency.WEEKLY:
            return from_date + timedelta(weeks=self.interval_value)
        elif self.frequency == RecurrenceFrequency.MONTHLY:
            # Add months (approximate - should use proper date math)
            return from_date + timedelta(days=30 * self.interval_value)
        elif self.frequency == RecurrenceFrequency.QUARTERLY:
            return from_date + timedelta(days=90 * self.interval_value)
        elif self.frequency == RecurrenceFrequency.YEARLY:
            return from_date + timedelta(days=365 * self.interval_value)
        else:
            # Custom logic would go here
            return from_date + timedelta(days=1)
    
    def should_generate_task(self, check_date=None):
        """Check if a new task should be generated"""
        if not self.is_active or self.is_paused:
            return False
        
        if check_date is None:
            check_date = datetime.utcnow()
        
        # Check if we've reached the end date or max occurrences
        if self.end_date and check_date > self.end_date:
            return False
        
        if self.max_occurrences and self.total_generated >= self.max_occurrences:
            return False
        
        # Check if it's time for the next task
        if self.next_due_date and check_date >= self.next_due_date:
            return True
        
        return False
    
    def __repr__(self):
        return f"<RecurringTaskTemplate(title='{self.title}', frequency='{self.frequency}')>"
