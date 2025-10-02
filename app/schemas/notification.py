"""Notification schemas for enhanced notification system"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from ..models.notification import NotificationType, NotificationPriority, NotificationChannel


class NotificationBase(BaseModel):
    title: str = Field(..., max_length=255)
    message: str
    short_description: Optional[str] = Field(None, max_length=500)
    notification_type: NotificationType
    priority: NotificationPriority = NotificationPriority.NORMAL
    category: Optional[str] = Field(None, max_length=100)
    
    # Related entities
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    context_card_id: Optional[str] = None
    decision_log_id: Optional[str] = None
    handoff_summary_id: Optional[str] = None
    
    # Smart features
    relevance_score: Optional[float] = Field(0.5, ge=0.0, le=1.0)
    context_data: Optional[Dict[str, Any]] = {}
    action_required: bool = False
    
    # Delivery settings
    delivery_channels: List[str] = []
    scheduled_for: Optional[datetime] = None
    timezone_aware: bool = True
    work_hours_only: bool = False
    
    # Metadata
    source: Optional[str] = Field(None, max_length=100)
    tags: List[str] = []
    expires_at: Optional[datetime] = None
    thread_id: Optional[str] = None
    parent_notification_id: Optional[str] = None


class NotificationCreate(NotificationBase):
    user_id: str


class NotificationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    message: Optional[str] = None
    priority: Optional[NotificationPriority] = None
    scheduled_for: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    tags: Optional[List[str]] = None


class NotificationMarkRead(BaseModel):
    notification_ids: List[str]


class NotificationFeedback(BaseModel):
    relevance_feedback: Optional[float] = Field(None, ge=0.0, le=1.0)
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    marked_as_spam: bool = False


class Notification(NotificationBase):
    id: str
    user_id: str
    organization_id: str
    auto_generated: bool
    
    # Status
    is_read: bool
    read_at: Optional[datetime]
    is_dismissed: bool
    dismissed_at: Optional[datetime]
    action_taken: bool
    action_taken_at: Optional[datetime]
    
    # Delivery tracking
    delivery_attempts: int
    delivered_channels: List[str]
    failed_channels: List[str]
    last_delivery_attempt: Optional[datetime]
    
    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationPreferenceBase(BaseModel):
    # Global settings
    enabled: bool = True
    focus_mode_enabled: bool = False
    focus_mode_start_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    focus_mode_end_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    focus_mode_days: List[str] = []
    
    # Work schedule
    work_start_time: str = Field("09:00", pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    work_end_time: str = Field("17:00", pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    work_days: List[str] = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    timezone: str = "UTC"
    
    # Urgency filters
    urgent_only_mode: bool = False
    minimum_priority: NotificationPriority = NotificationPriority.LOW
    
    # Digest settings
    daily_digest_enabled: bool = True
    daily_digest_time: str = Field("08:00", pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    weekly_digest_enabled: bool = False
    weekly_digest_day: str = "monday"
    weekly_digest_time: str = Field("08:00", pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    
    # Channel and type preferences
    channel_preferences: Dict[str, Any] = {}
    type_preferences: Dict[str, Any] = {}
    project_preferences: Dict[str, Any] = {}
    
    # Smart filtering
    ai_filtering_enabled: bool = True
    relevance_threshold: float = Field(0.3, ge=0.0, le=1.0)
    context_aware_grouping: bool = True

    @validator('focus_mode_days', 'work_days')
    def validate_days(cls, v):
        valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in v:
            if day.lower() not in valid_days:
                raise ValueError(f"Invalid day: {day}")
        return [day.lower() for day in v]


class NotificationPreferenceCreate(NotificationPreferenceBase):
    pass


class NotificationPreferenceUpdate(BaseModel):
    enabled: Optional[bool] = None
    focus_mode_enabled: Optional[bool] = None
    focus_mode_start_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    focus_mode_end_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    focus_mode_days: Optional[List[str]] = None
    work_start_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    work_end_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    work_days: Optional[List[str]] = None
    timezone: Optional[str] = None
    urgent_only_mode: Optional[bool] = None
    minimum_priority: Optional[NotificationPriority] = None
    daily_digest_enabled: Optional[bool] = None
    daily_digest_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    weekly_digest_enabled: Optional[bool] = None
    weekly_digest_day: Optional[str] = None
    weekly_digest_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    channel_preferences: Optional[Dict[str, Any]] = None
    type_preferences: Optional[Dict[str, Any]] = None
    project_preferences: Optional[Dict[str, Any]] = None
    ai_filtering_enabled: Optional[bool] = None
    relevance_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    context_aware_grouping: Optional[bool] = None


class NotificationPreference(NotificationPreferenceBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationRuleBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    conditions: Dict[str, Any]
    actions: Dict[str, Any]
    is_active: bool = True
    priority: int = 0


class NotificationRuleCreate(NotificationRuleBase):
    pass


class NotificationRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class NotificationRule(NotificationRuleBase):
    id: str
    user_id: str
    times_triggered: int
    last_triggered: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationSummaryResponse(BaseModel):
    total_notifications: int
    unread_count: int
    urgent_count: int
    notifications: List[Notification]
    grouped_notifications: Optional[Dict[str, List[Notification]]] = None


class FocusModeStatus(BaseModel):
    enabled: bool
    active_until: Optional[datetime] = None
    custom_duration_minutes: Optional[int] = None


class NotificationDigest(BaseModel):
    digest_type: str  # "daily" or "weekly"
    period_start: datetime
    period_end: datetime
    total_notifications: int
    urgent_notifications: List[Notification]
    project_summaries: Dict[str, Dict[str, Any]]
    top_actions_required: List[Notification]
    knowledge_highlights: List[Dict[str, Any]]


class SmartNotificationInsights(BaseModel):
    user_id: str
    period_days: int
    total_notifications: int
    engagement_rate: float
    average_relevance_score: float
    most_engaged_types: List[str]
    least_engaged_types: List[str]
    optimal_delivery_times: List[str]
    recommendations: List[str]
