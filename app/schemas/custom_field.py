from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum

class CustomFieldType(str, Enum):
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

class CustomFieldEntity(str, Enum):
    PROJECT = "project"
    TASK = "task"
    CUSTOMER = "customer"
    TEAM = "team"
    GOAL = "goal"
    PROPOSAL = "proposal"
    INVOICE = "invoice"
    VENDOR = "vendor"
    PURCHASE_ORDER = "purchase_order"

class CustomFieldOption(BaseModel):
    label: str = Field(..., description="Display label for the option")
    value: str = Field(..., description="Internal value for the option")
    color: Optional[str] = Field(None, description="Optional color for the option (hex code)")

class ValidationRules(BaseModel):
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None
    required: Optional[bool] = None

class CustomFieldBase(BaseModel):
    field_name: str = Field(..., max_length=100, description="Internal field name (snake_case)")
    field_label: str = Field(..., max_length=200, description="Display label for the field")
    entity_type: CustomFieldEntity = Field(..., description="Entity type this field applies to")
    field_type: CustomFieldType = Field(..., description="Type of the custom field")
    description: Optional[str] = Field(None, description="Optional description of the field")
    options: List[CustomFieldOption] = Field(default=[], description="Options for select/radio/multi-select fields")
    is_required: bool = Field(default=False, description="Whether this field is required")
    is_active: bool = Field(default=True, description="Whether this field is active")
    is_searchable: bool = Field(default=True, description="Whether this field can be searched")
    default_value: Optional[str] = Field(None, description="Default value for the field")
    validation_rules: Optional[ValidationRules] = Field(None, description="Validation rules for the field")
    display_order: int = Field(default=0, description="Order for displaying the field")

    @validator('field_name')
    def validate_field_name(cls, v):
        """Ensure field name follows naming conventions"""
        import re
        if not re.match(r'^[a-z][a-z0-9_]*$', v):
            raise ValueError('Field name must start with lowercase letter and contain only lowercase letters, numbers, and underscores')
        return v

    @validator('options')
    def validate_options(cls, v, values):
        """Ensure options are provided for fields that require them"""
        field_type = values.get('field_type')
        if field_type in [CustomFieldType.SELECT, CustomFieldType.MULTI_SELECT, CustomFieldType.RADIO]:
            if not v:
                raise ValueError(f'Options are required for field type {field_type}')
        return v

class CustomFieldCreate(CustomFieldBase):
    """Schema for creating a new custom field"""
    pass

class CustomFieldUpdate(BaseModel):
    """Schema for updating an existing custom field"""
    field_label: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    options: Optional[List[CustomFieldOption]] = None
    is_required: Optional[bool] = None
    is_active: Optional[bool] = None
    is_searchable: Optional[bool] = None
    default_value: Optional[str] = None
    validation_rules: Optional[ValidationRules] = None
    display_order: Optional[int] = None

class CustomField(CustomFieldBase):
    """Schema for returning custom field data"""
    id: str
    organization_id: str
    created_by_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CustomFieldList(BaseModel):
    """Schema for listing custom fields"""
    fields: List[CustomField]
    total: int
    page: int
    size: int

# Custom Field Value Schemas
class CustomFieldValueBase(BaseModel):
    custom_field_id: str = Field(..., description="ID of the custom field definition")
    entity_type: CustomFieldEntity = Field(..., description="Type of entity this value belongs to")
    entity_id: str = Field(..., description="ID of the entity instance")
    field_value: Optional[Any] = Field(None, description="The actual field value")

class CustomFieldValueCreate(CustomFieldValueBase):
    """Schema for creating/updating custom field values"""
    pass

class CustomFieldValue(CustomFieldValueBase):
    """Schema for returning custom field values"""
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class EntityCustomFields(BaseModel):
    """Schema for returning all custom field values for a specific entity"""
    entity_id: str
    entity_type: CustomFieldEntity
    values: Dict[str, Any] = Field(default={}, description="Custom field values keyed by field_name")

class CustomFieldTypeInfo(BaseModel):
    """Schema for returning information about available field types"""
    id: str
    name: str
    description: str
    has_options: bool
    supported_entities: List[CustomFieldEntity]

class CustomFieldStats(BaseModel):
    """Schema for custom field statistics"""
    total_fields: int
    fields_by_entity: Dict[str, int]
    fields_by_type: Dict[str, int]
    active_fields: int
    required_fields: int