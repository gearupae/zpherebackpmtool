from sqlalchemy import Column, String, Text, Boolean, Integer, JSON, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.models.base import Base
import uuid
import enum

class CustomFieldType(enum.Enum):
    TEXT = "text"
    TEXTAREA = "textarea" 
    NUMBER = "number"
    EMAIL = "email"
    DATE = "date"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    URL = "url"
    PHONE = "phone"
    CURRENCY = "currency"
    DATETIME = "datetime"
    USER = "user"
    FILE = "file"
    TAGS = "tags"

class CustomFieldEntity(enum.Enum):
    PROJECT = "project"
    TASK = "task"
    CUSTOMER = "customer"
    TEAM = "team"
    GOAL = "goal"
    PROPOSAL = "proposal"
    INVOICE = "invoice"
    VENDOR = "vendor"
    PURCHASE_ORDER = "purchase_order"

class CustomField(Base):
    """
    Custom fields that can be added to various entities in the system.
    This allows users to extend the standard data model with additional fields.
    """
    __tablename__ = "custom_fields"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Organization context
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Field identification
    field_name = Column(String(100), nullable=False)  # Internal name (e.g., "priority_level")
    field_label = Column(String(200), nullable=False)  # Display name (e.g., "Priority Level")
    
    # Field configuration
    entity_type = Column(SQLEnum(CustomFieldEntity), nullable=False)
    field_type = Column(SQLEnum(CustomFieldType), nullable=False)
    description = Column(Text)
    
    # Field options (for select, radio, multi-select fields)
    options = Column(JSON, default=list)  # [{"label": "High", "value": "high", "color": "#ff0000"}, ...]
    
    # Validation and constraints
    is_required = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_searchable = Column(Boolean, default=True)
    
    # Default and validation
    default_value = Column(Text)
    validation_rules = Column(JSON, default=dict)  # {"min_length": 5, "max_length": 100, "pattern": "regex"}
    
    # Display and ordering
    display_order = Column(Integer, default=0)
    
    # Audit fields
    created_by_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Add unique constraint for field_name within organization and entity_type
    __table_args__ = (
        {
            'indexes': [
                ('organization_id', 'entity_type'),
                ('organization_id', 'entity_type', 'field_name'),
            ]
        },
    )

class CustomFieldValue(Base):
    """
    Stores the actual values of custom fields for specific entity instances.
    This uses a flexible JSON storage approach.
    """
    __tablename__ = "custom_field_values"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Organization context
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Reference to the custom field definition
    custom_field_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Entity reference
    entity_type = Column(SQLEnum(CustomFieldEntity), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)  # The ID of the project, task, etc.
    
    # Field value (stored as JSON to handle different data types)
    field_value = Column(JSON)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Add unique constraint to prevent duplicate values for the same field on the same entity
    __table_args__ = (
        {
            'indexes': [
                ('organization_id', 'entity_type', 'entity_id'),
                ('custom_field_id', 'entity_id'),
            ]
        },
    )