"""Enhanced Notification System with Smart Features"""
import enum
from sqlalchemy import Column, String, Text, JSON, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from .base import UUIDBaseModel


class NotificationType(str, enum.Enum):
    """Types of notifications"""
    TASK_ASSIGNED = "task_assigned"
    TASK_STATUS_CHANGED = "task_status_changed"
    TASK_DUE_SOON = "task_due_soon"
    TASK_OVERDUE = "task_overdue"
    TASK_COMMENT = "task_comment"
    TASK_COMPLETED = "task_completed"
    
    PROJECT_STATUS_CHANGED = "project_status_changed"
    PROJECT_MILESTONE = "project_milestone"
    PROJECT_DEADLINE = "project_deadline"
    PROJECT_MEMBER_ADDED = "project_member_added"
    PROJECT_COMMENT = "project_comment"
    
    HANDOFF_RECEIVED = "handoff_received"
    HANDOFF_REVIEWED = "handoff_reviewed"
    HANDOFF_REMINDER = "handoff_reminder"
    
    DECISION_LOGGED = "decision_logged"
    DECISION_REVIEW_DUE = "decision_review_due"
    DECISION_STATUS_CHANGED = "decision_status_changed"
    
    CONTEXT_CARD_LINKED = "context_card_linked"
    KNOWLEDGE_ARTICLE_SHARED = "knowledge_article_shared"
    
    MENTION = "mention"
    SYSTEM_ALERT = "system_alert"
    REMINDER = "reminder"
    URGENT_ACTION_REQUIRED = "urgent_action_required"


class NotificationPriority(str, enum.Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class NotificationChannel(str, enum.Enum):
    """Notification delivery channels"""
    IN_APP = "in_app"
    EMAIL = "email"
    PUSH = "push"
    SLACK = "slack"
    TEAMS = "teams"
    SMS = "sms"
    WEBHOOK = "webhook"


class Notification(UUIDBaseModel):
    """Enhanced notification model with smart features"""
    __tablename__ = "notifications"
    
    # Basic notification info
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    short_description = Column(String(500))  # For brief summaries
    
    # Classification
    notification_type = Column(SQLEnum(NotificationType), nullable=False)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.NORMAL)
    category = Column(String(100))  # Custom categorization
    
    # Recipients
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Related entities
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    context_card_id = Column(String, ForeignKey("context_cards.id"), nullable=True)
    decision_log_id = Column(String, ForeignKey("decision_logs.id"), nullable=True)
    handoff_summary_id = Column(String, ForeignKey("handoff_summaries.id"), nullable=True)
    
    # Smart features
    relevance_score = Column(Float, default=0.5)  # AI-powered relevance (0-1)
    context_data = Column(JSON, default=dict)  # Background context
    action_required = Column(Boolean, default=False)
    auto_generated = Column(Boolean, default=False)
    
    # Delivery and timing
    delivery_channels = Column(JSON, default=list)  # List of channels to deliver to
    scheduled_for = Column(DateTime(timezone=True))  # Scheduled delivery time
    timezone_aware = Column(Boolean, default=True)
    work_hours_only = Column(Boolean, default=False)
    
    # Status and interaction
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))
    is_dismissed = Column(Boolean, default=False)
    dismissed_at = Column(DateTime(timezone=True))
    action_taken = Column(Boolean, default=False)
    action_taken_at = Column(DateTime(timezone=True))
    
    # Delivery tracking
    delivery_attempts = Column(Integer, default=0)
    delivered_channels = Column(JSON, default=list)  # Successful deliveries
    failed_channels = Column(JSON, default=list)  # Failed deliveries
    last_delivery_attempt = Column(DateTime(timezone=True))
    
    # Grouping and threading
    thread_id = Column(String)  # Group related notifications
    parent_notification_id = Column(String, ForeignKey("notifications.id"))
    
    # Metadata
    source = Column(String(100))  # What generated this notification
    tags = Column(JSON, default=list)
    expires_at = Column(DateTime(timezone=True))  # Auto-cleanup
    
    # Relationships
    user = relationship("User")
    organization = relationship("Organization")
    project = relationship("Project")
    task = relationship("Task")
    context_card = relationship("ContextCard")
    decision_log = relationship("DecisionLog")
    handoff_summary = relationship("HandoffSummary")
    parent_notification = relationship("Notification", remote_side="Notification.id")

    def __repr__(self):
        return f"<Notification(title='{self.title}', type='{self.notification_type}', user='{self.user_id}')>"


class NotificationPreference(UUIDBaseModel):
    """User notification preferences with granular controls"""
    __tablename__ = "notification_preferences"
    
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Global settings
    enabled = Column(Boolean, default=True)
    focus_mode_enabled = Column(Boolean, default=False)
    focus_mode_start_time = Column(String(10))  # HH:MM format
    focus_mode_end_time = Column(String(10))  # HH:MM format
    focus_mode_days = Column(JSON, default=list)  # Days of week
    
    # Work schedule for timezone-aware delivery
    work_start_time = Column(String(10), default="09:00")
    work_end_time = Column(String(10), default="17:00")
    work_days = Column(JSON, default=["monday", "tuesday", "wednesday", "thursday", "friday"])
    timezone = Column(String(50), default="UTC")
    
    # Urgency filters
    urgent_only_mode = Column(Boolean, default=False)
    minimum_priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.LOW)
    
    # Digest settings
    daily_digest_enabled = Column(Boolean, default=True)
    daily_digest_time = Column(String(10), default="08:00")
    weekly_digest_enabled = Column(Boolean, default=False)
    weekly_digest_day = Column(String(10), default="monday")
    weekly_digest_time = Column(String(10), default="08:00")
    
    # Channel preferences
    channel_preferences = Column(JSON, default=dict)  # Per-type channel settings
    
    # Type-specific settings
    type_preferences = Column(JSON, default=dict)  # Per-notification-type settings
    
    # Project-specific preferences
    project_preferences = Column(JSON, default=dict)  # Per-project notification settings
    
    # Smart filtering
    ai_filtering_enabled = Column(Boolean, default=True)
    relevance_threshold = Column(Float, default=0.3)  # Minimum relevance score
    context_aware_grouping = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<NotificationPreference(user_id='{self.user_id}', enabled='{self.enabled}')>"


class NotificationRule(UUIDBaseModel):
    """Custom notification rules for advanced filtering"""
    __tablename__ = "notification_rules"
    
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Rule conditions
    conditions = Column(JSON, nullable=False)  # Complex rule conditions
    actions = Column(JSON, nullable=False)  # Actions to take when conditions match
    
    # Metadata
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Rule execution priority
    
    # Usage tracking
    times_triggered = Column(Integer, default=0)
    last_triggered = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<NotificationRule(name='{self.name}', user_id='{self.user_id}')>"


class NotificationAnalytics(UUIDBaseModel):
    """Analytics for notification engagement and optimization"""
    __tablename__ = "notification_analytics"
    
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    notification_id = Column(String, ForeignKey("notifications.id"), nullable=False)
    
    # Interaction tracking
    opened_at = Column(DateTime(timezone=True))
    time_to_open = Column(Integer)  # Seconds from delivery to open
    clicked_at = Column(DateTime(timezone=True))
    time_to_click = Column(Integer)  # Seconds from delivery to click
    
    # Engagement metrics
    relevance_feedback = Column(Float)  # User feedback on relevance (0-1)
    user_rating = Column(Integer)  # User rating (1-5)
    marked_as_spam = Column(Boolean, default=False)
    
    # Context
    device_type = Column(String(50))
    channel_used = Column(String(50))
    time_of_day = Column(Integer)  # Hour of day (0-23)
    day_of_week = Column(Integer)  # Day of week (0-6)
    
    # Relationships
    user = relationship("User")
    notification = relationship("Notification")

    def __repr__(self):
        return f"<NotificationAnalytics(user_id='{self.user_id}', notification_id='{self.notification_id}')>"
