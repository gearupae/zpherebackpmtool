from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Enum, Table, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import UUIDBaseModel
import enum
from typing import Optional

# Association table for goal members
goal_members = Table(
    'goal_members',
    UUIDBaseModel.metadata,
    Column('goal_id', String, ForeignKey('goal.id', ondelete='CASCADE'), primary_key=True),
    Column('user_id', String, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('role', String, default='member'),  # member, owner, viewer
    Column('created_at', DateTime(timezone=True), server_default=func.now())
)

class GoalType(str, enum.Enum):
    PERSONAL = "personal"
    TEAM = "team"
    SALES = "sales"
    PROJECT = "project"
    CUSTOM = "custom"

class GoalStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"

class GoalPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ReminderInterval(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

class Goal(UUIDBaseModel):
    __tablename__ = "goal"
    
    # Basic Information
    title = Column(String, nullable=False, index=True)
    description = Column(Text)
    
    # Dates
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    
    # Goal Classification
    goal_type = Column(Enum(GoalType), default=GoalType.PERSONAL)
    status = Column(Enum(GoalStatus), default=GoalStatus.NOT_STARTED)
    priority = Column(Enum(GoalPriority), default=GoalPriority.MEDIUM)
    
    # Progress Tracking
    target_value = Column(Float, default=0)  # For quantitative goals (e.g., sales target)
    current_value = Column(Float, default=0)  # Current progress
    unit = Column(String)  # Unit of measurement (pieces, dollars, percentage, etc.)
    completion_percentage = Column(Float, default=0.0)
    
    # Metadata
    created_by = Column(String, ForeignKey('users.id'), nullable=False)
    organization_id = Column(String, ForeignKey('organizations.id'))
    project_id = Column(String, ForeignKey('projects.id'), nullable=True)  # Optional project association
    
    # Additional Configuration
    is_archived = Column(Boolean, default=False)
    auto_update_progress = Column(Boolean, default=False)  # For sales/product goals
    tags = Column(JSON, default=list)  # Flexible tagging system
    # Use DB column name 'metadata' but Python attribute 'meta' to avoid SQLAlchemy reserved name conflict
    meta = Column('metadata', JSON, default=dict)  # Store additional custom data
    
    # Relationships
    members = relationship("User", secondary=goal_members, back_populates="goals")
    checklists = relationship("GoalChecklist", back_populates="goal", cascade="all, delete-orphan")
    progress_logs = relationship("GoalProgress", back_populates="goal", cascade="all, delete-orphan")
    reminders = relationship("GoalReminder", back_populates="goal", cascade="all, delete-orphan")
    
    def calculate_completion_percentage(self):
        """Calculate completion percentage based on checklists and target values"""
        if self.target_value and self.target_value > 0:
            return min(100.0, (self.current_value / self.target_value) * 100)
        
        # Calculate based on completed checklists
        if self.checklists:
            completed_items = sum(1 for item in self.checklists if item.is_completed)
            total_items = len(self.checklists)
            return (completed_items / total_items) * 100 if total_items > 0 else 0.0
        
        return self.completion_percentage or 0.0
    
    def get_probability_of_achievement(self):
        """Calculate probability of achieving the goal based on current progress and time remaining"""
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        
        # If goal is already completed
        if self.status == GoalStatus.COMPLETED:
            return 100.0
        
        # If goal is overdue or cancelled
        if self.status in [GoalStatus.OVERDUE, GoalStatus.CANCELLED]:
            return 0.0
        
        # Calculate time-based factors
        total_duration = (self.end_date - self.start_date).total_seconds()
        elapsed_time = (now - self.start_date).total_seconds()
        remaining_time = (self.end_date - now).total_seconds()
        
        if remaining_time <= 0:
            return 0.0  # Goal is overdue
        
        time_progress = elapsed_time / total_duration if total_duration > 0 else 1.0
        completion_progress = self.calculate_completion_percentage() / 100.0
        
        # Simple probability calculation
        if time_progress == 0:
            return completion_progress * 100
        
        progress_rate = completion_progress / time_progress if time_progress > 0 else 0
        
        # Adjust probability based on progress rate
        if progress_rate >= 1.0:
            probability = min(95.0, completion_progress * 100 + (progress_rate - 1) * 20)
        else:
            probability = completion_progress * 100 * progress_rate
        
        return max(0.0, min(100.0, probability))

class GoalChecklist(UUIDBaseModel):
    __tablename__ = "goal_checklist"
    
    goal_id = Column(String, ForeignKey('goal.id', ondelete='CASCADE'), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True))
    completed_by = Column(String, ForeignKey('users.id'))
    due_date = Column(DateTime(timezone=True))
    priority = Column(Enum(GoalPriority), default=GoalPriority.MEDIUM)
    order_index = Column(Integer, default=0)
    
    # Relationships
    goal = relationship("Goal", back_populates="checklists")

class GoalProgress(UUIDBaseModel):
    __tablename__ = "goal_progress"
    
    goal_id = Column(String, ForeignKey('goal.id', ondelete='CASCADE'), nullable=False)
    previous_value = Column(Float, default=0)
    new_value = Column(Float, default=0)
    change_amount = Column(Float, default=0)
    notes = Column(Text)
    created_by = Column(String, ForeignKey('users.id'), nullable=False)

    
    # Automatic tracking fields
    source = Column(String)  # manual, automatic, integration
    reference_id = Column(String)  # ID from external system if auto-updated
    
    # Relationships
    goal = relationship("Goal", back_populates="progress_logs")

class GoalReminder(UUIDBaseModel):
    __tablename__ = "goal_reminder"
    
    goal_id = Column(String, ForeignKey('goal.id', ondelete='CASCADE'), nullable=False)
    interval = Column(Enum(ReminderInterval), default=ReminderInterval.WEEKLY)
    custom_interval_days = Column(Integer)  # For custom intervals
    is_active = Column(Boolean, default=True)
    last_sent_at = Column(DateTime(timezone=True))
    next_reminder_at = Column(DateTime(timezone=True))
    reminder_message = Column(Text)
    
    # Notification preferences
    send_email = Column(Boolean, default=True)
    send_in_app = Column(Boolean, default=True)
    send_to_members = Column(Boolean, default=True)  # Send to all goal members
    
    # Relationships
    goal = relationship("Goal", back_populates="reminders")
    
    def calculate_next_reminder(self):
        """Calculate the next reminder date based on interval"""
        from datetime import datetime, timedelta, timezone
        
        if not self.is_active:
            return None
        
        base_date = self.last_sent_at or datetime.now(timezone.utc)
        
        if self.interval == ReminderInterval.DAILY:
            return base_date + timedelta(days=1)
        elif self.interval == ReminderInterval.WEEKLY:
            return base_date + timedelta(weeks=1)
        elif self.interval == ReminderInterval.BIWEEKLY:
            return base_date + timedelta(weeks=2)
        elif self.interval == ReminderInterval.MONTHLY:
            return base_date + timedelta(days=30)
        elif self.interval == ReminderInterval.CUSTOM and self.custom_interval_days:
            return base_date + timedelta(days=self.custom_interval_days)
        
        return None
