"""User Dashboard Preferences Models"""
import enum
from sqlalchemy import Column, String, JSON, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import UUIDBaseModel


class DashboardLayoutType(str, enum.Enum):
    """Dashboard layout types"""
    GRID = "grid"
    LIST = "list"
    KANBAN = "kanban"
    CALENDAR = "calendar"
    GANTT = "gantt"
    TIMELINE = "timeline"


class DashboardWidgetType(str, enum.Enum):
    """Available dashboard widget types"""
    PROJECT_STATUS = "project_status"
    TASK_OVERVIEW = "task_overview"
    TEAM_PERFORMANCE = "team_performance"
    RECENT_ACTIVITY = "recent_activity"
    UPCOMING_DEADLINES = "upcoming_deadlines"
    MY_TASKS = "my_tasks"
    TIME_TRACKING = "time_tracking"
    BUDGET_OVERVIEW = "budget_overview"
    PRIORITY_MATRIX = "priority_matrix"
    VELOCITY_CHART = "velocity_chart"
    CUSTOM_ANALYTICS = "custom_analytics"


class UserDashboardPreference(UUIDBaseModel):
    """User dashboard preferences and customization"""
    __tablename__ = "user_dashboard_preferences"
    
    # User relationship
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Layout preferences
    default_layout = Column(SQLEnum(DashboardLayoutType), default=DashboardLayoutType.GRID)
    task_view_preference = Column(SQLEnum(DashboardLayoutType), default=DashboardLayoutType.LIST)
    project_view_preference = Column(SQLEnum(DashboardLayoutType), default=DashboardLayoutType.GRID)
    
    # Widget configuration
    enabled_widgets = Column(JSON, default=list)  # List of enabled widget types
    widget_positions = Column(JSON, default=dict)  # Widget position and size configuration
    widget_settings = Column(JSON, default=dict)  # Individual widget settings
    
    # Display preferences
    items_per_page = Column(Integer, default=20)
    show_completed_tasks = Column(Boolean, default=False)
    show_archived_projects = Column(Boolean, default=False)
    compact_mode = Column(Boolean, default=False)
    
    # Custom filters and views
    saved_filters = Column(JSON, default=dict)  # Saved filter configurations
    favorite_views = Column(JSON, default=list)  # Favorite view configurations
    quick_actions = Column(JSON, default=list)  # Customized quick actions
    
    # Notification preferences (dashboard-specific)
    dashboard_notifications = Column(JSON, default=dict)
    
    # Theme and appearance
    color_scheme = Column(String, default="default")
    custom_colors = Column(JSON, default=dict)
    
    # Relationships
    user = relationship("User", back_populates="dashboard_preferences")
    
    def __repr__(self):
        return f"<UserDashboardPreference(user_id='{self.user_id}', layout='{self.default_layout}')>"


class DashboardWidget(UUIDBaseModel):
    """Custom dashboard widgets"""
    __tablename__ = "dashboard_widgets"
    
    # Widget metadata
    name = Column(String(255), nullable=False)
    description = Column(String(500))
    widget_type = Column(SQLEnum(DashboardWidgetType), nullable=False)
    
    # Creator and organization
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Widget configuration
    config = Column(JSON, default=dict)  # Widget-specific configuration
    data_source = Column(JSON, default=dict)  # Data source configuration
    refresh_interval = Column(Integer, default=300)  # Refresh interval in seconds
    
    # Display settings
    default_size = Column(JSON, default={"width": 4, "height": 3})  # Grid size
    min_size = Column(JSON, default={"width": 2, "height": 2})
    max_size = Column(JSON, default={"width": 12, "height": 6})
    
    # Sharing and permissions
    is_public = Column(Boolean, default=False)
    is_template = Column(Boolean, default=False)
    allowed_roles = Column(JSON, default=list)  # User roles that can use this widget
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    created_by = relationship("User")
    organization = relationship("Organization")
    
    def __repr__(self):
        return f"<DashboardWidget(name='{self.name}', type='{self.widget_type}')>"


class CustomField(UUIDBaseModel):
    """Custom fields for projects and tasks"""
    __tablename__ = "custom_fields"
    
    # Field metadata
    name = Column(String(255), nullable=False)
    field_key = Column(String(100), nullable=False)  # Unique key for the field
    description = Column(String(500))
    
    # Organization and scope
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Field configuration
    field_type = Column(String(50), nullable=False)  # text, number, date, select, multi_select, boolean, etc.
    field_options = Column(JSON, default=dict)  # Options for select fields, validation rules, etc.
    default_value = Column(JSON)  # Default value for the field
    
    # Scope and applicability
    applies_to = Column(JSON, default=list)  # ['projects', 'tasks', 'customers', etc.]
    required_for = Column(JSON, default=list)  # Contexts where field is required
    
    # Display settings
    display_order = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)
    is_searchable = Column(Boolean, default=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    organization = relationship("Organization")
    created_by = relationship("User")
    
    def __repr__(self):
        return f"<CustomField(name='{self.name}', type='{self.field_type}')>"


class WorkflowTemplate(UUIDBaseModel):
    """Workflow templates for common project types"""
    __tablename__ = "workflow_templates"
    
    # Template metadata
    name = Column(String(255), nullable=False)
    description = Column(String(1000))
    category = Column(String(100))  # e.g., 'software_development', 'marketing', 'consulting'
    
    # Creator and organization
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Template content
    template_data = Column(JSON, nullable=False)  # Complete template structure
    default_settings = Column(JSON, default=dict)  # Default project settings
    custom_fields = Column(JSON, default=list)  # Custom fields included in template
    
    # Template configuration
    estimated_duration_days = Column(Integer)
    complexity_level = Column(String(20), default="medium")  # low, medium, high
    required_roles = Column(JSON, default=list)  # Required team roles
    
    # Usage and sharing
    usage_count = Column(Integer, default=0)
    is_public = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    tags = Column(JSON, default=list)
    
    # Template structure
    phases = Column(JSON, default=list)  # Project phases/milestones
    task_templates = Column(JSON, default=list)  # Task templates
    dependencies = Column(JSON, default=list)  # Task dependencies
    
    # Status
    is_active = Column(Boolean, default=True)
    version = Column(String(20), default="1.0")
    
    # Relationships
    created_by = relationship("User")
    organization = relationship("Organization")
    
    def __repr__(self):
        return f"<WorkflowTemplate(name='{self.name}', category='{self.category}')>"


class UserWorkflowPreference(UUIDBaseModel):
    """User preferences for workflows and processes"""
    __tablename__ = "user_workflow_preferences"
    
    # User relationship
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Workflow preferences
    preferred_task_statuses = Column(JSON, default=list)  # Custom task status workflow
    preferred_project_phases = Column(JSON, default=list)  # Custom project phases
    default_estimation_method = Column(String(50), default="story_points")  # story_points, hours, t_shirt
    
    # Automation preferences
    auto_assign_tasks = Column(Boolean, default=False)
    auto_update_progress = Column(Boolean, default=True)
    auto_close_completed = Column(Boolean, default=False)
    
    # Notification workflows
    workflow_notifications = Column(JSON, default=dict)
    escalation_rules = Column(JSON, default=list)
    
    # Custom workflows
    personal_workflows = Column(JSON, default=list)  # User-defined workflows
    
    # Relationships
    user = relationship("User", back_populates="workflow_preferences")
    
    def __repr__(self):
        return f"<UserWorkflowPreference(user_id='{self.user_id}')>"
