"""Integration Hub Models for External Tool Connectivity"""
import enum
from sqlalchemy import Column, String, Text, JSON, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import UUIDBaseModel


class IntegrationType(str, enum.Enum):
    """Types of integrations"""
    SLACK = "slack"
    TEAMS = "teams"
    DISCORD = "discord"
    EMAIL = "email"
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    JIRA = "jira"
    TRELLO = "trello"
    ASANA = "asana"
    NOTION = "notion"
    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"
    ONEDRIVE = "onedrive"
    CALENDAR = "calendar"
    ZOOM = "zoom"
    CUSTOM_WEBHOOK = "custom_webhook"
    REST_API = "rest_api"


class IntegrationStatus(str, enum.Enum):
    """Integration connection status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING_AUTH = "pending_auth"
    RATE_LIMITED = "rate_limited"
    SUSPENDED = "suspended"


class SyncDirection(str, enum.Enum):
    """Data synchronization direction"""
    BIDIRECTIONAL = "bidirectional"
    INBOUND_ONLY = "inbound_only"
    OUTBOUND_ONLY = "outbound_only"


class ActivityType(str, enum.Enum):
    """Types of activities in the unified stream"""
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    COMMENT_ADDED = "comment_added"
    FILE_UPLOADED = "file_uploaded"
    INTEGRATION_EVENT = "integration_event"
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"


class Integration(UUIDBaseModel):
    """External tool integrations"""
    __tablename__ = "integrations"
    
    # Integration metadata
    name = Column(String(255), nullable=False)
    description = Column(Text)
    integration_type = Column(SQLEnum(IntegrationType), nullable=False)
    
    # Organization and user
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Connection details
    status = Column(SQLEnum(IntegrationStatus), default=IntegrationStatus.INACTIVE)
    external_service_id = Column(String(255))  # External service account/workspace ID
    external_service_name = Column(String(255))  # Human readable name
    
    # Authentication and credentials
    auth_type = Column(String(50))  # oauth, api_key, webhook, etc.
    encrypted_credentials = Column(Text)  # Encrypted auth tokens/keys
    auth_expires_at = Column(DateTime(timezone=True))
    
    # Configuration
    config = Column(JSON, default=dict)  # Integration-specific configuration
    sync_direction = Column(SQLEnum(SyncDirection), default=SyncDirection.BIDIRECTIONAL)
    sync_frequency_minutes = Column(Integer, default=15)  # Sync frequency
    
    # Data mapping and filters
    field_mappings = Column(JSON, default=dict)  # Field mapping between systems
    data_filters = Column(JSON, default=dict)  # Filters for what data to sync
    webhook_url = Column(String(500))  # Webhook URL for real-time updates
    
    # Status and monitoring
    last_sync_at = Column(DateTime(timezone=True))
    last_sync_status = Column(String(50))  # success, error, partial
    sync_error_count = Column(Integer, default=0)
    last_error_message = Column(Text)
    
    # Usage statistics
    total_syncs = Column(Integer, default=0)
    successful_syncs = Column(Integer, default=0)
    data_synced_count = Column(Integer, default=0)
    
    # Settings
    is_active = Column(Boolean, default=True)
    auto_retry_on_error = Column(Boolean, default=True)
    notification_on_error = Column(Boolean, default=True)
    
    # Relationships
    organization = relationship("Organization")
    created_by = relationship("User")
    sync_logs = relationship("IntegrationSyncLog", back_populates="integration")
    
    def __repr__(self):
        return f"<Integration(name='{self.name}', type='{self.integration_type}')>"


class IntegrationSyncLog(UUIDBaseModel):
    """Logs for integration synchronization activities"""
    __tablename__ = "integration_sync_logs"
    
    # Integration relationship
    integration_id = Column(String, ForeignKey("integrations.id"), nullable=False)
    
    # Sync details
    sync_start_time = Column(DateTime(timezone=True), nullable=False)
    sync_end_time = Column(DateTime(timezone=True))
    sync_duration_seconds = Column(Float)
    
    # Sync results
    sync_status = Column(String(50), nullable=False)  # success, error, partial, cancelled
    records_processed = Column(Integer, default=0)
    records_created = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    
    # Error information
    error_message = Column(Text)
    error_details = Column(JSON, default=dict)
    retry_count = Column(Integer, default=0)
    
    # Data details
    sync_type = Column(String(50))  # manual, scheduled, webhook, real_time
    data_summary = Column(JSON, default=dict)  # Summary of what was synced
    
    # Relationships
    integration = relationship("Integration", back_populates="sync_logs")
    
    def __repr__(self):
        return f"<IntegrationSyncLog(integration_id='{self.integration_id}', status='{self.sync_status}')>"


class UniversalSearch(UUIDBaseModel):
    """Universal search index across all integrated tools"""
    __tablename__ = "universal_search"
    
    # Search metadata
    content_id = Column(String(255), nullable=False)  # Unique ID for the content
    content_type = Column(String(100), nullable=False)  # task, project, file, comment, etc.
    source_system = Column(String(100), nullable=False)  # zphere, slack, github, etc.
    
    # Organization scope
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Content details
    title = Column(String(500))
    content = Column(Text)  # Searchable content
    description = Column(Text)
    tags = Column(JSON, default=list)
    
    # Context information
    project_id = Column(String)  # Associated project if any
    created_by_id = Column(String)  # Creator user ID
    related_users = Column(JSON, default=list)  # Related user IDs
    
    # Timestamps
    content_created_at = Column(DateTime(timezone=True))
    content_updated_at = Column(DateTime(timezone=True))
    last_indexed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # URL and access
    external_url = Column(String(1000))  # Direct link to content
    internal_url = Column(String(1000))  # Internal app link if applicable
    access_permissions = Column(JSON, default=list)  # Who can access this content
    
    # Search optimization
    search_weight = Column(Float, default=1.0)  # Search result weight/priority
    is_searchable = Column(Boolean, default=True)
    search_keywords = Column(JSON, default=list)  # Additional keywords for search
    
    # Relationships
    organization = relationship("Organization")
    
    def __repr__(self):
        return f"<UniversalSearch(content_id='{self.content_id}', type='{self.content_type}')>"


class ActivityStream(UUIDBaseModel):
    """Unified activity stream from all tools"""
    __tablename__ = "activity_stream"
    
    # Activity metadata
    activity_type = Column(SQLEnum(ActivityType), nullable=False)
    source_system = Column(String(100), nullable=False)  # Which system generated this
    external_id = Column(String(255))  # ID in the external system
    
    # Organization and user context
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"))  # User who performed the action
    
    # Activity details
    title = Column(String(500), nullable=False)
    description = Column(Text)
    activity_data = Column(JSON, default=dict)  # Structured activity data
    
    # Context and relationships
    project_id = Column(String)  # Related project if any
    task_id = Column(String)  # Related task if any
    related_entity_type = Column(String(100))  # Type of related entity
    related_entity_id = Column(String(255))  # ID of related entity
    
    # Timestamps
    activity_timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Display and interaction
    is_public = Column(Boolean, default=True)
    importance_score = Column(Float, default=1.0)  # For prioritizing in feeds
    read_by = Column(JSON, default=list)  # Users who have seen this activity
    
    # External links
    external_url = Column(String(1000))  # Link to activity in external system
    thumbnail_url = Column(String(1000))  # Thumbnail image if applicable
    
    # Relationships
    organization = relationship("Organization")
    user = relationship("User")
    
    def __repr__(self):
        return f"<ActivityStream(type='{self.activity_type}', system='{self.source_system}')>"


class SmartConnector(UUIDBaseModel):
    """Smart connectors for advanced integration logic"""
    __tablename__ = "smart_connectors"
    
    # Connector metadata
    name = Column(String(255), nullable=False)
    description = Column(Text)
    connector_type = Column(String(100), nullable=False)  # sync, automation, trigger
    
    # Organization and creator
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Connector configuration
    source_integration_id = Column(String, ForeignKey("integrations.id"))
    target_integration_id = Column(String, ForeignKey("integrations.id"))
    connector_logic = Column(JSON, nullable=False)  # Business logic rules
    
    # Trigger conditions
    trigger_events = Column(JSON, default=list)  # Events that trigger this connector
    trigger_conditions = Column(JSON, default=dict)  # Conditions to evaluate
    
    # Actions and transformations
    actions = Column(JSON, default=list)  # Actions to perform
    data_transformations = Column(JSON, default=dict)  # How to transform data
    
    # Execution settings
    is_active = Column(Boolean, default=True)
    execution_order = Column(Integer, default=0)  # Order of execution
    max_retries = Column(Integer, default=3)
    
    # Performance tracking
    execution_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    avg_execution_time_ms = Column(Float)
    
    # Relationships
    organization = relationship("Organization")
    created_by = relationship("User")
    source_integration = relationship("Integration", foreign_keys=[source_integration_id])
    target_integration = relationship("Integration", foreign_keys=[target_integration_id])
    
    def __repr__(self):
        return f"<SmartConnector(name='{self.name}', type='{self.connector_type}')>"


class QuickAction(UUIDBaseModel):
    """Quick actions for context switching minimization"""
    __tablename__ = "quick_actions"
    
    # Action metadata
    name = Column(String(255), nullable=False)
    description = Column(Text)
    action_type = Column(String(100), nullable=False)  # create_task, send_message, etc.
    
    # User and organization
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Action configuration
    target_system = Column(String(100))  # Which system this action targets
    action_config = Column(JSON, nullable=False)  # Action configuration
    default_values = Column(JSON, default=dict)  # Default values for quick creation
    
    # UI configuration
    icon = Column(String(100))  # Icon for the action
    shortcut_key = Column(String(20))  # Keyboard shortcut
    context_filters = Column(JSON, default=dict)  # When to show this action
    
    # Usage and access
    usage_count = Column(Integer, default=0)
    is_favorite = Column(Boolean, default=False)
    is_public = Column(Boolean, default=False)
    allowed_roles = Column(JSON, default=list)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    organization = relationship("Organization")
    created_by = relationship("User")
    
    def __repr__(self):
        return f"<QuickAction(name='{self.name}', type='{self.action_type}')>"
