"""Integration Hub Schemas"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from ..models.integration_hub import (
    IntegrationType, IntegrationStatus, SyncDirection, ActivityType
)


class IntegrationBase(BaseModel):
    """Base integration schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    integration_type: IntegrationType
    external_service_name: Optional[str] = Field(None, max_length=255)


class IntegrationCreate(IntegrationBase):
    """Create integration schema"""
    auth_type: Optional[str] = Field(None, max_length=50)
    config: Dict[str, Any] = {}
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    sync_frequency_minutes: int = Field(default=15, ge=1, le=1440)
    field_mappings: Dict[str, Any] = {}
    data_filters: Dict[str, Any] = {}
    webhook_url: Optional[HttpUrl] = None
    auto_retry_on_error: bool = True
    notification_on_error: bool = True


class IntegrationUpdate(BaseModel):
    """Update integration schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[IntegrationStatus] = None
    external_service_name: Optional[str] = Field(None, max_length=255)
    config: Optional[Dict[str, Any]] = None
    sync_direction: Optional[SyncDirection] = None
    sync_frequency_minutes: Optional[int] = Field(None, ge=1, le=1440)
    field_mappings: Optional[Dict[str, Any]] = None
    data_filters: Optional[Dict[str, Any]] = None
    webhook_url: Optional[HttpUrl] = None
    is_active: Optional[bool] = None
    auto_retry_on_error: Optional[bool] = None
    notification_on_error: Optional[bool] = None


class Integration(IntegrationBase):
    """Integration schema with all fields"""
    id: str
    organization_id: str
    created_by_id: str
    status: IntegrationStatus
    external_service_id: Optional[str]
    auth_type: Optional[str]
    auth_expires_at: Optional[datetime]
    config: Dict[str, Any]
    sync_direction: SyncDirection
    sync_frequency_minutes: int
    field_mappings: Dict[str, Any]
    data_filters: Dict[str, Any]
    webhook_url: Optional[str]
    last_sync_at: Optional[datetime]
    last_sync_status: Optional[str]
    sync_error_count: int
    last_error_message: Optional[str]
    total_syncs: int
    successful_syncs: int
    data_synced_count: int
    is_active: bool
    auto_retry_on_error: bool
    notification_on_error: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class IntegrationSyncLogBase(BaseModel):
    """Base integration sync log schema"""
    sync_start_time: datetime
    sync_status: str = Field(..., max_length=50)
    records_processed: int = Field(default=0, ge=0)
    records_created: int = Field(default=0, ge=0)
    records_updated: int = Field(default=0, ge=0)
    records_failed: int = Field(default=0, ge=0)


class IntegrationSyncLogCreate(IntegrationSyncLogBase):
    """Create integration sync log schema"""
    integration_id: str
    sync_end_time: Optional[datetime] = None
    sync_duration_seconds: Optional[float] = Field(None, ge=0)
    error_message: Optional[str] = None
    error_details: Dict[str, Any] = {}
    retry_count: int = Field(default=0, ge=0)
    sync_type: Optional[str] = Field(None, max_length=50)
    data_summary: Dict[str, Any] = {}


class IntegrationSyncLog(IntegrationSyncLogBase):
    """Integration sync log schema with all fields"""
    id: str
    integration_id: str
    sync_end_time: Optional[datetime]
    sync_duration_seconds: Optional[float]
    error_message: Optional[str]
    error_details: Dict[str, Any]
    retry_count: int
    sync_type: Optional[str]
    data_summary: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True


class UniversalSearchBase(BaseModel):
    """Base universal search schema"""
    content_id: str = Field(..., max_length=255)
    content_type: str = Field(..., max_length=100)
    source_system: str = Field(..., max_length=100)
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    description: Optional[str] = None


class UniversalSearchCreate(UniversalSearchBase):
    """Create universal search schema"""
    tags: List[str] = []
    project_id: Optional[str] = None
    created_by_id: Optional[str] = None
    related_users: List[str] = []
    content_created_at: Optional[datetime] = None
    content_updated_at: Optional[datetime] = None
    external_url: Optional[HttpUrl] = None
    internal_url: Optional[str] = None
    access_permissions: List[str] = []
    search_weight: float = Field(default=1.0, ge=0, le=10)
    search_keywords: List[str] = []


class UniversalSearchUpdate(BaseModel):
    """Update universal search schema"""
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    project_id: Optional[str] = None
    related_users: Optional[List[str]] = None
    content_updated_at: Optional[datetime] = None
    external_url: Optional[HttpUrl] = None
    internal_url: Optional[str] = None
    access_permissions: Optional[List[str]] = None
    search_weight: Optional[float] = Field(None, ge=0, le=10)
    is_searchable: Optional[bool] = None
    search_keywords: Optional[List[str]] = None


class UniversalSearch(UniversalSearchBase):
    """Universal search schema with all fields"""
    id: str
    organization_id: str
    tags: List[str]
    project_id: Optional[str]
    created_by_id: Optional[str]
    related_users: List[str]
    content_created_at: Optional[datetime]
    content_updated_at: Optional[datetime]
    last_indexed_at: datetime
    external_url: Optional[str]
    internal_url: Optional[str]
    access_permissions: List[str]
    search_weight: float
    is_searchable: bool
    search_keywords: List[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ActivityStreamBase(BaseModel):
    """Base activity stream schema"""
    activity_type: ActivityType
    source_system: str = Field(..., max_length=100)
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    activity_timestamp: datetime


class ActivityStreamCreate(ActivityStreamBase):
    """Create activity stream schema"""
    external_id: Optional[str] = Field(None, max_length=255)
    user_id: Optional[str] = None
    activity_data: Dict[str, Any] = {}
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    related_entity_type: Optional[str] = Field(None, max_length=100)
    related_entity_id: Optional[str] = Field(None, max_length=255)
    is_public: bool = True
    importance_score: float = Field(default=1.0, ge=0, le=10)
    external_url: Optional[HttpUrl] = None
    thumbnail_url: Optional[HttpUrl] = None


class ActivityStream(ActivityStreamBase):
    """Activity stream schema with all fields"""
    id: str
    external_id: Optional[str]
    organization_id: str
    user_id: Optional[str]
    activity_data: Dict[str, Any]
    project_id: Optional[str]
    task_id: Optional[str]
    related_entity_type: Optional[str]
    related_entity_id: Optional[str]
    is_public: bool
    importance_score: float
    read_by: List[str]
    external_url: Optional[str]
    thumbnail_url: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class SmartConnectorBase(BaseModel):
    """Base smart connector schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    connector_type: str = Field(..., max_length=100)


class SmartConnectorCreate(SmartConnectorBase):
    """Create smart connector schema"""
    source_integration_id: Optional[str] = None
    target_integration_id: Optional[str] = None
    connector_logic: Dict[str, Any] = {}
    trigger_events: List[str] = []
    trigger_conditions: Dict[str, Any] = {}
    actions: List[Dict[str, Any]] = []
    data_transformations: Dict[str, Any] = {}
    execution_order: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0, le=10)


class SmartConnectorUpdate(BaseModel):
    """Update smart connector schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    source_integration_id: Optional[str] = None
    target_integration_id: Optional[str] = None
    connector_logic: Optional[Dict[str, Any]] = None
    trigger_events: Optional[List[str]] = None
    trigger_conditions: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, Any]]] = None
    data_transformations: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    execution_order: Optional[int] = Field(None, ge=0)
    max_retries: Optional[int] = Field(None, ge=0, le=10)


class SmartConnector(SmartConnectorBase):
    """Smart connector schema with all fields"""
    id: str
    organization_id: str
    created_by_id: str
    source_integration_id: Optional[str]
    target_integration_id: Optional[str]
    connector_logic: Dict[str, Any]
    trigger_events: List[str]
    trigger_conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    data_transformations: Dict[str, Any]
    is_active: bool
    execution_order: int
    max_retries: int
    execution_count: int
    success_count: int
    error_count: int
    avg_execution_time_ms: Optional[float]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class QuickActionBase(BaseModel):
    """Base quick action schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    action_type: str = Field(..., max_length=100)
    target_system: Optional[str] = Field(None, max_length=100)


class QuickActionCreate(QuickActionBase):
    """Create quick action schema"""
    action_config: Dict[str, Any] = {}
    default_values: Dict[str, Any] = {}
    icon: Optional[str] = Field(None, max_length=100)
    shortcut_key: Optional[str] = Field(None, max_length=20)
    context_filters: Dict[str, Any] = {}
    is_public: bool = False
    allowed_roles: List[str] = []


class QuickActionUpdate(BaseModel):
    """Update quick action schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    action_config: Optional[Dict[str, Any]] = None
    default_values: Optional[Dict[str, Any]] = None
    icon: Optional[str] = Field(None, max_length=100)
    shortcut_key: Optional[str] = Field(None, max_length=20)
    context_filters: Optional[Dict[str, Any]] = None
    is_favorite: Optional[bool] = None
    is_public: Optional[bool] = None
    allowed_roles: Optional[List[str]] = None
    is_active: Optional[bool] = None


class QuickAction(QuickActionBase):
    """Quick action schema with all fields"""
    id: str
    organization_id: str
    created_by_id: str
    action_config: Dict[str, Any]
    default_values: Dict[str, Any]
    icon: Optional[str]
    shortcut_key: Optional[str]
    context_filters: Dict[str, Any]
    usage_count: int
    is_favorite: bool
    is_public: bool
    allowed_roles: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Search and analysis schemas
class SearchQuery(BaseModel):
    """Universal search query"""
    query: str = Field(..., min_length=1)
    content_types: Optional[List[str]] = None
    source_systems: Optional[List[str]] = None
    project_id: Optional[str] = None
    date_range: Optional[Dict[str, datetime]] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchResult(BaseModel):
    """Search result item"""
    id: str
    content_id: str
    content_type: str
    source_system: str
    title: str
    content: str
    description: Optional[str]
    relevance_score: float
    external_url: Optional[str]
    internal_url: Optional[str]
    created_at: datetime
    highlights: List[str]


class SearchResponse(BaseModel):
    """Search response with results"""
    query: str
    total_results: int
    results: List[SearchResult]
    facets: Dict[str, List[Dict[str, Any]]]
    suggestions: List[str]
    execution_time_ms: float


class IntegrationStats(BaseModel):
    """Integration statistics"""
    integration_id: str
    total_syncs: int
    successful_syncs: int
    failed_syncs: int
    success_rate: float
    avg_sync_duration: float
    last_sync: Optional[datetime]
    data_synced_count: int
    error_trends: List[Dict[str, Any]]


class ActivityFeed(BaseModel):
    """Activity feed response"""
    activities: List[ActivityStream]
    total_count: int
    unread_count: int
    has_more: bool
    next_cursor: Optional[str]


class ConnectorExecution(BaseModel):
    """Connector execution result"""
    connector_id: str
    execution_id: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[float]
    trigger_event: str
    actions_executed: List[str]
    results: Dict[str, Any]
    error_message: Optional[str]
