from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Enum, DateTime, JSON, Integer, Float
from sqlalchemy.orm import relationship
import enum
from .base import UUIDBaseModel


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, enum.Enum):
    TASK = "task"
    BUG = "bug"
    FEATURE = "feature"
    EPIC = "epic"
    STORY = "story"
    SUBTASK = "subtask"


class Task(UUIDBaseModel):
    """Task model"""
    __tablename__ = "tasks"
    
    # Basic task info
    title = Column(String(500), nullable=False)
    description = Column(Text)
    
    # Project relationship
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    # Task details
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM)
    task_type = Column(Enum(TaskType), default=TaskType.TASK)
    
    # Assignment and ownership
    assignee_id = Column(String, ForeignKey("users.id"))
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Hierarchy (for subtasks and dependencies)
    parent_task_id = Column(String, ForeignKey("tasks.id"))
    position = Column(Integer, default=0)  # For ordering
    
    # Recurring task relationship
    recurring_template_id = Column(String, ForeignKey("recurring_task_templates.id"))
    
    # Dates and time tracking
    start_date = Column(DateTime(timezone=True))
    due_date = Column(DateTime(timezone=True))
    completed_date = Column(DateTime(timezone=True))
    
    # Sprint (simple, non-relational)
    sprint_name = Column(String(255))
    sprint_start_date = Column(DateTime(timezone=True))
    sprint_end_date = Column(DateTime(timezone=True))
    sprint_goal = Column(Text)
    
    # Estimation and tracking
    estimated_hours = Column(Float)
    actual_hours = Column(Float, default=0.0)
    story_points = Column(Integer)
    
    # Labels and categorization
    labels = Column(JSON, default=list)  # List of label names
    tags = Column(JSON, default=list)  # List of tags
    
    # Custom fields and metadata
    custom_fields = Column(JSON, default=dict)
    task_metadata = Column(JSON, default=dict)  # For storing additional context
    
    # Flags
    is_recurring = Column(Boolean, default=False)
    is_template = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    # Public visibility for client/shared views
    visible_to_customer = Column(Boolean, default=False)
    
    # Relationships
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_tasks")
    created_by = relationship("User", foreign_keys=[created_by_id], back_populates="created_tasks")
    
    # Multiple assignees support
    assignees = relationship("TaskAssignee", back_populates="task", cascade="all, delete-orphan")
    
    # Watchers and notifications
    watchers = relationship("TaskWatcher", back_populates="task", cascade="all, delete-orphan")
    
    # Self-referential relationships for hierarchy
    parent_task = relationship("Task", remote_side="Task.id", back_populates="subtasks")
    subtasks = relationship("Task", back_populates="parent_task")
    
    # Dependencies
    blocked_by = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.dependent_task_id",
        back_populates="dependent_task"
    )
    blocks = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.prerequisite_task_id",
        back_populates="prerequisite_task"
    )
    
    # Comments, attachments, and documents
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")
    attachments = relationship("TaskAttachment", back_populates="task", cascade="all, delete-orphan")
    documents = relationship("TaskDocument", back_populates="task", cascade="all, delete-orphan")
    
    # Knowledge management relationships
    context_cards = relationship("ContextCard", back_populates="task", cascade="all, delete-orphan")
    handoff_summaries = relationship("HandoffSummary", back_populates="task", cascade="all, delete-orphan")
    
    # Recurring task relationship
    recurring_template = relationship("RecurringTaskTemplate", back_populates="generated_tasks")
    
    @property
    def is_overdue(self):
        if not self.due_date:
            return False
        from datetime import datetime
        return datetime.utcnow() > self.due_date and self.status != TaskStatus.COMPLETED
    
    @property
    def completion_percentage(self):
        if not self.subtasks:
            return 100 if self.status == TaskStatus.COMPLETED else 0
        
        completed_subtasks = sum(1 for subtask in self.subtasks if subtask.status == TaskStatus.COMPLETED)
        return (completed_subtasks / len(self.subtasks)) * 100
    
    def __repr__(self):
        return f"<Task(title='{self.title}', status='{self.status}')>"


class TaskDependency(UUIDBaseModel):
    """Task dependency model for task relationships"""
    __tablename__ = "task_dependencies"
    
    prerequisite_task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    dependent_task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    dependency_type = Column(String(50), default="blocks")  # blocks, follows, relates_to
    
    # Relationships
    prerequisite_task = relationship("Task", foreign_keys=[prerequisite_task_id], back_populates="blocks")
    dependent_task = relationship("Task", foreign_keys=[dependent_task_id], back_populates="blocked_by")
    
    def __repr__(self):
        return f"<TaskDependency(prerequisite='{self.prerequisite_task_id}', dependent='{self.dependent_task_id}')>"


class TaskComment(UUIDBaseModel):
    """Task comment model"""
    __tablename__ = "task_comments"
    
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    
    # Threading support
    parent_comment_id = Column(String, ForeignKey("task_comments.id"))
    
    # Mention support
    mentions = Column(JSON, default=list)  # List of user IDs mentioned
    
    # Task links
    linked_tasks = Column(JSON, default=list)  # List of task IDs linked in the comment
    
    # Flags
    is_edited = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    
    # Relationships
    task = relationship("Task", back_populates="comments")
    user = relationship("User")
    parent_comment = relationship("TaskComment", remote_side="TaskComment.id")
    replies = relationship("TaskComment", back_populates="parent_comment")
    
    def __repr__(self):
        return f"<TaskComment(task_id='{self.task_id}', user_id='{self.user_id}')>"


class TaskAttachment(UUIDBaseModel):
    """Task attachment model"""
    __tablename__ = "task_attachments"
    
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100))
    
    # Relationships
    task = relationship("Task", back_populates="attachments")
    user = relationship("User")
    
    def __repr__(self):
        return f"<TaskAttachment(filename='{self.filename}', task_id='{self.task_id}')>"


class TaskWatcher(UUIDBaseModel):
    """Task watcher model for users who want to be notified about task updates"""
    __tablename__ = "task_watchers"
    
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Watcher settings
    notify_on_comment = Column(Boolean, default=True)
    notify_on_status_change = Column(Boolean, default=True)
    notify_on_assignment = Column(Boolean, default=True)
    notify_on_due_date = Column(Boolean, default=True)
    
    # Relationships
    task = relationship("Task", back_populates="watchers")
    user = relationship("User")
    
    def __repr__(self):
        return f"<TaskWatcher(task_id='{self.task_id}', user_id='{self.user_id}')>"
