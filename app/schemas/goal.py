from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from ..models.goal import GoalType, GoalStatus, GoalPriority, ReminderInterval

# Base schemas for common fields
class GoalBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    start_date: datetime
    end_date: datetime
    goal_type: GoalType = GoalType.PERSONAL
    priority: GoalPriority = GoalPriority.MEDIUM
    target_value: Optional[float] = 0
    unit: Optional[str] = Field(None, max_length=50)
    project_id: Optional[str] = None
    auto_update_progress: bool = False
    tags: List[str] = []
    metadata: Dict[str, Any] = {}

    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('End date must be after start date')
        return v

    @validator('target_value')
    def target_value_positive(cls, v):
        if v is not None and v < 0:
            raise ValueError('Target value must be positive')
        return v

class GoalCreate(GoalBase):
    member_ids: List[str] = []
    checklist_items: List[Dict[str, Any]] = []
    reminder_settings: Optional[Dict[str, Any]] = None

class GoalUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    goal_type: Optional[GoalType] = None
    status: Optional[GoalStatus] = None
    priority: Optional[GoalPriority] = None
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    unit: Optional[str] = Field(None, max_length=50)
    project_id: Optional[str] = None
    auto_update_progress: Optional[bool] = None
    is_archived: Optional[bool] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

    @validator('target_value', 'current_value')
    def values_positive(cls, v):
        if v is not None and v < 0:
            raise ValueError('Values must be positive')
        return v

# User information schema for goal members
class GoalMemberInfo(BaseModel):
    id: str
    username: str
    first_name: str
    last_name: str
    email: str
    avatar_url: Optional[str] = None
    role: str = "member"  # member, owner, viewer

    class Config:
        from_attributes = True

class GoalMemberAdd(BaseModel):
    user_id: str
    role: Optional[str] = "member"

    @validator('role')
    def validate_role(cls, v):
        allowed = {"member", "owner", "viewer"}
        if v not in allowed:
            raise ValueError(f"Role must be one of {sorted(allowed)}")
        return v

class GoalMembersAdd(BaseModel):
    members: List[GoalMemberAdd] = []

class GoalMemberUpdate(BaseModel):
    role: str

    @validator('role')
    def validate_role(cls, v):
        allowed = {"member", "owner", "viewer"}
        if v not in allowed:
            raise ValueError(f"Role must be one of {sorted(allowed)}")
        return v

# Goal checklist schemas
class GoalChecklistBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    due_date: Optional[datetime] = None
    priority: GoalPriority = GoalPriority.MEDIUM
    order_index: int = 0

class GoalChecklistCreate(GoalChecklistBase):
    pass

class GoalChecklistUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    is_completed: Optional[bool] = None
    due_date: Optional[datetime] = None
    priority: Optional[GoalPriority] = None
    order_index: Optional[int] = None

class GoalChecklist(GoalChecklistBase):
    id: str
    goal_id: str
    is_completed: bool
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Goal progress schemas
class GoalProgressBase(BaseModel):
    new_value: float
    notes: Optional[str] = Field(None, max_length=1000)
    source: str = "manual"  # manual, automatic, integration
    reference_id: Optional[str] = None

class GoalProgressCreate(GoalProgressBase):
    pass

class GoalProgress(GoalProgressBase):
    id: str
    goal_id: str
    previous_value: float
    change_amount: float
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True

# Goal reminder schemas
class GoalReminderBase(BaseModel):
    interval: ReminderInterval = ReminderInterval.WEEKLY
    custom_interval_days: Optional[int] = None
    is_active: bool = True
    reminder_message: Optional[str] = Field(None, max_length=500)
    send_email: bool = True
    send_in_app: bool = True
    send_to_members: bool = True

    @validator('custom_interval_days')
    def validate_custom_interval(cls, v, values):
        if values.get('interval') == ReminderInterval.CUSTOM and (v is None or v <= 0):
            raise ValueError('Custom interval days must be positive when using custom interval')
        return v

class GoalReminderCreate(GoalReminderBase):
    pass

class GoalReminderUpdate(BaseModel):
    interval: Optional[ReminderInterval] = None
    custom_interval_days: Optional[int] = None
    is_active: Optional[bool] = None
    reminder_message: Optional[str] = Field(None, max_length=500)
    send_email: Optional[bool] = None
    send_in_app: Optional[bool] = None
    send_to_members: Optional[bool] = None

class GoalReminder(GoalReminderBase):
    id: str
    goal_id: str
    last_sent_at: Optional[datetime] = None
    next_reminder_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Main goal response schemas
class Goal(GoalBase):
    id: str
    status: GoalStatus
    current_value: float
    completion_percentage: float
    created_by: str
    organization_id: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    probability_of_achievement: float
    days_remaining: int
    is_overdue: bool
    
    # Related data
    members: List[GoalMemberInfo] = []
    checklists: List[GoalChecklist] = []
    recent_progress: List[GoalProgress] = []
    active_reminders: List[GoalReminder] = []

    @validator('probability_of_achievement', pre=True, always=True)
    def calculate_probability(cls, v, values):
        # This will be calculated in the API response
        return v or 0.0

    @validator('days_remaining', pre=True, always=True)
    def calculate_days_remaining(cls, v, values):
        if 'end_date' in values and values['end_date']:
            now = datetime.now(timezone.utc)
            if values['end_date'].tzinfo is None:
                end_date = values['end_date'].replace(tzinfo=timezone.utc)
            else:
                end_date = values['end_date']
            
            delta = end_date - now
            return max(0, delta.days)
        return 0

    @validator('is_overdue', pre=True, always=True)
    def calculate_is_overdue(cls, v, values):
        if 'end_date' in values and 'status' in values:
            now = datetime.now(timezone.utc)
            if values['end_date'].tzinfo is None:
                end_date = values['end_date'].replace(tzinfo=timezone.utc)
            else:
                end_date = values['end_date']
            
            return (now > end_date and 
                   values.get('status') not in [GoalStatus.COMPLETED, GoalStatus.CANCELLED])
        return False

    class Config:
        from_attributes = True

class GoalSummary(BaseModel):
    """Lightweight goal summary for lists and cards"""
    id: str
    title: str
    description: Optional[str] = None
    goal_type: GoalType
    status: GoalStatus
    priority: GoalPriority
    start_date: datetime
    end_date: datetime
    completion_percentage: float
    probability_of_achievement: float
    days_remaining: int
    is_overdue: bool
    member_count: int
    checklist_count: int
    completed_checklist_count: int
    target_value: Optional[float] = None
    current_value: float
    unit: Optional[str] = None
    tags: List[str] = []

    class Config:
        from_attributes = True

# Analytics and metrics schemas
class GoalMetrics(BaseModel):
    total_goals: int
    active_goals: int
    completed_goals: int
    overdue_goals: int
    average_completion_rate: float
    goals_by_type: Dict[str, int]
    goals_by_priority: Dict[str, int]
    upcoming_deadlines: List[GoalSummary]
    high_probability_goals: List[GoalSummary]
    low_probability_goals: List[GoalSummary]

class GoalFilters(BaseModel):
    status: Optional[List[GoalStatus]] = None
    goal_type: Optional[List[GoalType]] = None
    priority: Optional[List[GoalPriority]] = None
    member_id: Optional[str] = None
    project_id: Optional[str] = None
    tags: Optional[List[str]] = None
    overdue_only: Optional[bool] = None
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    search: Optional[str] = None

# Bulk operations
class BulkGoalUpdate(BaseModel):
    goal_ids: List[str]
    updates: GoalUpdate

class BulkGoalArchive(BaseModel):
    goal_ids: List[str]
    archive: bool = True

# Goal templates (for common goal types)
class GoalTemplate(BaseModel):
    name: str
    description: str
    goal_type: GoalType
    default_duration_days: int
    checklist_template: List[Dict[str, Any]]
    default_reminder_settings: Dict[str, Any]
    suggested_tags: List[str]
    metadata_schema: Dict[str, Any] = {}

class GoalFromTemplate(BaseModel):
    template_name: str
    title: str
    start_date: datetime
    custom_data: Dict[str, Any] = {}
    member_ids: List[str] = []
