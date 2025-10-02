"""User Dashboard and Workflow Schemas"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from ..models.user_dashboard import DashboardLayoutType, DashboardWidgetType


class DashboardPreferencesBase(BaseModel):
    """Base dashboard preferences schema"""
    default_layout: DashboardLayoutType = DashboardLayoutType.GRID
    task_view_preference: DashboardLayoutType = DashboardLayoutType.LIST
    project_view_preference: DashboardLayoutType = DashboardLayoutType.GRID
    items_per_page: int = Field(default=20, ge=5, le=100)
    show_completed_tasks: bool = False
    show_archived_projects: bool = False
    compact_mode: bool = False
    color_scheme: str = "default"


class DashboardPreferencesCreate(DashboardPreferencesBase):
    """Create dashboard preferences schema"""
    enabled_widgets: List[DashboardWidgetType] = []
    widget_positions: Dict[str, Any] = {}
    widget_settings: Dict[str, Any] = {}
    saved_filters: Dict[str, Any] = {}
    favorite_views: List[str] = []
    quick_actions: List[str] = []
    dashboard_notifications: Dict[str, Any] = {}
    custom_colors: Dict[str, Any] = {}


class DashboardPreferencesUpdate(BaseModel):
    """Update dashboard preferences schema"""
    default_layout: Optional[DashboardLayoutType] = None
    task_view_preference: Optional[DashboardLayoutType] = None
    project_view_preference: Optional[DashboardLayoutType] = None
    enabled_widgets: Optional[List[DashboardWidgetType]] = None
    widget_positions: Optional[Dict[str, Any]] = None
    widget_settings: Optional[Dict[str, Any]] = None
    items_per_page: Optional[int] = Field(None, ge=5, le=100)
    show_completed_tasks: Optional[bool] = None
    show_archived_projects: Optional[bool] = None
    compact_mode: Optional[bool] = None
    saved_filters: Optional[Dict[str, Any]] = None
    favorite_views: Optional[List[str]] = None
    quick_actions: Optional[List[str]] = None
    dashboard_notifications: Optional[Dict[str, Any]] = None
    color_scheme: Optional[str] = None
    custom_colors: Optional[Dict[str, Any]] = None


class DashboardPreferences(DashboardPreferencesBase):
    """Dashboard preferences schema with all fields"""
    id: str
    user_id: str
    enabled_widgets: List[DashboardWidgetType]
    widget_positions: Dict[str, Any]
    widget_settings: Dict[str, Any]
    saved_filters: Dict[str, Any]
    favorite_views: List[str]
    quick_actions: List[str]
    dashboard_notifications: Dict[str, Any]
    custom_colors: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DashboardWidgetBase(BaseModel):
    """Base dashboard widget schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    widget_type: DashboardWidgetType
    refresh_interval: int = Field(default=300, ge=30, le=3600)
    is_public: bool = False
    is_template: bool = False


class DashboardWidgetCreate(DashboardWidgetBase):
    """Create dashboard widget schema"""
    config: Dict[str, Any] = {}
    data_source: Dict[str, Any] = {}
    default_size: Dict[str, int] = {"width": 4, "height": 3}
    min_size: Dict[str, int] = {"width": 2, "height": 2}
    max_size: Dict[str, int] = {"width": 12, "height": 6}
    allowed_roles: List[str] = []


class DashboardWidgetUpdate(BaseModel):
    """Update dashboard widget schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    config: Optional[Dict[str, Any]] = None
    data_source: Optional[Dict[str, Any]] = None
    refresh_interval: Optional[int] = Field(None, ge=30, le=3600)
    default_size: Optional[Dict[str, int]] = None
    min_size: Optional[Dict[str, int]] = None
    max_size: Optional[Dict[str, int]] = None
    is_public: Optional[bool] = None
    is_template: Optional[bool] = None
    allowed_roles: Optional[List[str]] = None
    is_active: Optional[bool] = None


class DashboardWidget(DashboardWidgetBase):
    """Dashboard widget schema with all fields"""
    id: str
    created_by_id: str
    organization_id: str
    config: Dict[str, Any]
    data_source: Dict[str, Any]
    default_size: Dict[str, int]
    min_size: Dict[str, int]
    max_size: Dict[str, int]
    allowed_roles: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CustomFieldBase(BaseModel):
    """Base custom field schema"""
    name: str = Field(..., min_length=1, max_length=255)
    field_key: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    field_type: str = Field(..., pattern="^(text|number|date|select|multi_select|boolean|textarea|url|email)$")
    display_order: int = 0
    is_visible: bool = True
    is_searchable: bool = True


class CustomFieldCreate(CustomFieldBase):
    """Create custom field schema"""
    field_options: Dict[str, Any] = {}
    default_value: Optional[Any] = None
    applies_to: List[str] = []
    required_for: List[str] = []


class CustomFieldUpdate(BaseModel):
    """Update custom field schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    field_options: Optional[Dict[str, Any]] = None
    default_value: Optional[Any] = None
    applies_to: Optional[List[str]] = None
    required_for: Optional[List[str]] = None
    display_order: Optional[int] = None
    is_visible: Optional[bool] = None
    is_searchable: Optional[bool] = None
    is_active: Optional[bool] = None


class CustomField(CustomFieldBase):
    """Custom field schema with all fields"""
    id: str
    organization_id: str
    created_by_id: str
    field_options: Dict[str, Any]
    default_value: Optional[Any]
    applies_to: List[str]
    required_for: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WorkflowTemplateBase(BaseModel):
    """Base workflow template schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)
    estimated_duration_days: Optional[int] = Field(None, ge=1)
    complexity_level: str = Field(default="medium", pattern="^(low|medium|high)$")
    is_public: bool = False
    is_featured: bool = False


class WorkflowTemplateCreate(WorkflowTemplateBase):
    """Create workflow template schema"""
    template_data: Dict[str, Any] = {}
    default_settings: Dict[str, Any] = {}
    custom_fields: List[str] = []
    required_roles: List[str] = []
    tags: List[str] = []
    phases: List[Dict[str, Any]] = []
    task_templates: List[Dict[str, Any]] = []
    dependencies: List[Dict[str, Any]] = []


class WorkflowTemplateUpdate(BaseModel):
    """Update workflow template schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)
    template_data: Optional[Dict[str, Any]] = None
    default_settings: Optional[Dict[str, Any]] = None
    custom_fields: Optional[List[str]] = None
    estimated_duration_days: Optional[int] = Field(None, ge=1)
    complexity_level: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    required_roles: Optional[List[str]] = None
    is_public: Optional[bool] = None
    is_featured: Optional[bool] = None
    tags: Optional[List[str]] = None
    phases: Optional[List[Dict[str, Any]]] = None
    task_templates: Optional[List[Dict[str, Any]]] = None
    dependencies: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None


class WorkflowTemplate(WorkflowTemplateBase):
    """Workflow template schema with all fields"""
    id: str
    created_by_id: str
    organization_id: str
    template_data: Dict[str, Any]
    default_settings: Dict[str, Any]
    custom_fields: List[str]
    required_roles: List[str]
    usage_count: int
    tags: List[str]
    phases: List[Dict[str, Any]]
    task_templates: List[Dict[str, Any]]
    dependencies: List[Dict[str, Any]]
    is_active: bool
    version: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserWorkflowPreferencesBase(BaseModel):
    """Base user workflow preferences schema"""
    default_estimation_method: str = Field(default="story_points", pattern="^(story_points|hours|t_shirt)$")
    auto_assign_tasks: bool = False
    auto_update_progress: bool = True
    auto_close_completed: bool = False
    monitoring_frequency: str = Field(default="weekly", pattern="^(daily|weekly|monthly)$")


class UserWorkflowPreferencesCreate(UserWorkflowPreferencesBase):
    """Create user workflow preferences schema"""
    preferred_task_statuses: List[str] = []
    preferred_project_phases: List[str] = []
    workflow_notifications: Dict[str, Any] = {}
    escalation_rules: List[Dict[str, Any]] = []
    personal_workflows: List[Dict[str, Any]] = []


class UserWorkflowPreferencesUpdate(BaseModel):
    """Update user workflow preferences schema"""
    preferred_task_statuses: Optional[List[str]] = None
    preferred_project_phases: Optional[List[str]] = None
    default_estimation_method: Optional[str] = Field(None, pattern="^(story_points|hours|t_shirt)$")
    auto_assign_tasks: Optional[bool] = None
    auto_update_progress: Optional[bool] = None
    auto_close_completed: Optional[bool] = None
    workflow_notifications: Optional[Dict[str, Any]] = None
    escalation_rules: Optional[List[Dict[str, Any]]] = None
    personal_workflows: Optional[List[Dict[str, Any]]] = None


class UserWorkflowPreferences(UserWorkflowPreferencesBase):
    """User workflow preferences schema with all fields"""
    id: str
    user_id: str
    preferred_task_statuses: List[str]
    preferred_project_phases: List[str]
    workflow_notifications: Dict[str, Any]
    escalation_rules: List[Dict[str, Any]]
    personal_workflows: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Summary schemas for dashboard
class DashboardSummary(BaseModel):
    """Dashboard summary data"""
    total_projects: int
    active_projects: int
    completed_projects: int
    overdue_projects: int
    total_tasks: int
    my_tasks: int
    completed_tasks: int
    overdue_tasks: int
    team_members: int
    upcoming_deadlines: List[Dict[str, Any]]
    recent_activity: List[Dict[str, Any]]


class WidgetData(BaseModel):
    """Widget data response"""
    widget_id: str
    widget_type: DashboardWidgetType
    data: Dict[str, Any]
    last_updated: datetime
    next_update: datetime
