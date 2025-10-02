from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from ....api.deps_tenant import get_current_tenant_db as get_current_tenant_db, get_current_user_from_tenant
from app.models.custom_field import CustomField, CustomFieldValue, CustomFieldType, CustomFieldEntity
from app.models.user import User
from app.schemas.custom_field import (
    CustomFieldCreate,
    CustomFieldUpdate,
    CustomField as CustomFieldSchema,
    CustomFieldList,
    CustomFieldValueCreate,
    CustomFieldValue as CustomFieldValueSchema,
    EntityCustomFields,
    CustomFieldTypeInfo,
    CustomFieldStats
)

router = APIRouter()

@router.get("/types", response_model=List[CustomFieldTypeInfo])
async def get_custom_field_types():
    """Get information about available custom field types"""
    field_types = [
        {
            "id": "text",
            "name": "Text",
            "description": "Single line text input",
            "has_options": False,
            "supported_entities": [e.value for e in CustomFieldEntity]
        },
        {
            "id": "textarea",
            "name": "Long Text",
            "description": "Multi-line text area",
            "has_options": False,
            "supported_entities": [e.value for e in CustomFieldEntity]
        },
        {
            "id": "number",
            "name": "Number",
            "description": "Numeric input with validation",
            "has_options": False,
            "supported_entities": [e.value for e in CustomFieldEntity]
        },
        {
            "id": "email",
            "name": "Email",
            "description": "Email address with validation",
            "has_options": False,
            "supported_entities": ["customer", "vendor", "team"]
        },
        {
            "id": "phone",
            "name": "Phone",
            "description": "Phone number input",
            "has_options": False,
            "supported_entities": ["customer", "vendor", "team"]
        },
        {
            "id": "select",
            "name": "Dropdown",
            "description": "Single selection from predefined options",
            "has_options": True,
            "supported_entities": [e.value for e in CustomFieldEntity]
        },
        {
            "id": "multi_select",
            "name": "Multi-Select",
            "description": "Multiple selections from predefined options",
            "has_options": True,
            "supported_entities": [e.value for e in CustomFieldEntity]
        },
        {
            "id": "radio",
            "name": "Radio Buttons",
            "description": "Single selection with radio buttons",
            "has_options": True,
            "supported_entities": [e.value for e in CustomFieldEntity]
        },
        {
            "id": "checkbox",
            "name": "Checkbox",
            "description": "True/false checkbox",
            "has_options": False,
            "supported_entities": [e.value for e in CustomFieldEntity]
        },
        {
            "id": "date",
            "name": "Date",
            "description": "Date picker",
            "has_options": False,
            "supported_entities": [e.value for e in CustomFieldEntity]
        },
        {
            "id": "url",
            "name": "URL",
            "description": "Web URL with validation",
            "has_options": False,
            "supported_entities": [e.value for e in CustomFieldEntity]
        },
    ]
    return field_types

@router.get("/stats", response_model=CustomFieldStats)
async def get_custom_field_stats(
    entity_type: Optional[CustomFieldEntity] = None,
    db: Session = Depends(get_current_tenant_db),
    current_user: User = Depends(get_current_user_from_tenant)
):
    """Get statistics about custom fields"""
    query = db.query(CustomField).filter(CustomField.organization_id == current_user.organization_id)
    
    if entity_type:
        query = query.filter(CustomField.entity_type == entity_type)
    
    all_fields = query.all()
    
    fields_by_entity = {}
    fields_by_type = {}
    active_fields = 0
    required_fields = 0
    
    for field in all_fields:
        # Count by entity
        entity_str = field.entity_type.value
        fields_by_entity[entity_str] = fields_by_entity.get(entity_str, 0) + 1
        
        # Count by type
        type_str = field.field_type.value
        fields_by_type[type_str] = fields_by_type.get(type_str, 0) + 1
        
        # Count active and required
        if field.is_active:
            active_fields += 1
        if field.is_required:
            required_fields += 1
    
    return CustomFieldStats(
        total_fields=len(all_fields),
        fields_by_entity=fields_by_entity,
        fields_by_type=fields_by_type,
        active_fields=active_fields,
        required_fields=required_fields
    )

@router.get("/", response_model=CustomFieldList)
async def get_custom_fields(
    entity_type: Optional[CustomFieldEntity] = None,
    active_only: bool = Query(True, description="Only return active fields"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_current_tenant_db),
    current_user: User = Depends(get_current_user_from_tenant)
):
    """Get custom fields for the current organization"""
    query = db.query(CustomField).filter(
        CustomField.organization_id == current_user.organization_id
    )
    
    if entity_type:
        query = query.filter(CustomField.entity_type == entity_type)
    
    if active_only:
        query = query.filter(CustomField.is_active == True)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    fields = query.order_by(
        CustomField.entity_type,
        CustomField.display_order,
        CustomField.field_label
    ).offset((page - 1) * size).limit(size).all()
    
    return CustomFieldList(
        fields=fields,
        total=total,
        page=page,
        size=size
    )

@router.post("/", response_model=CustomFieldSchema)
async def create_custom_field(
    field_data: CustomFieldCreate,
    db: Session = Depends(get_current_tenant_db),
    current_user: User = Depends(get_current_user_from_tenant)
):
    """Create a new custom field"""
    # Check if field name already exists for this entity type
    existing_field = db.query(CustomField).filter(
        and_(
            CustomField.organization_id == current_user.organization_id,
            CustomField.entity_type == field_data.entity_type,
            CustomField.field_name == field_data.field_name
        )
    ).first()
    
    if existing_field:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Custom field '{field_data.field_name}' already exists for {field_data.entity_type.value}"
        )
    
    # Create new custom field
    db_field = CustomField(
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
        **field_data.dict()
    )
    
    db.add(db_field)
    db.commit()
    db.refresh(db_field)
    
    return db_field

@router.get("/{field_id}", response_model=CustomFieldSchema)
async def get_custom_field(
    field_id: str,
    db: Session = Depends(get_current_tenant_db),
    current_user: User = Depends(get_current_user_from_tenant)
):
    """Get a specific custom field"""
    field = db.query(CustomField).filter(
        and_(
            CustomField.id == field_id,
            CustomField.organization_id == current_user.organization_id
        )
    ).first()
    
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom field not found"
        )
    
    return field

@router.put("/{field_id}", response_model=CustomFieldSchema)
async def update_custom_field(
    field_id: str,
    field_data: CustomFieldUpdate,
    db: Session = Depends(get_current_tenant_db),
    current_user: User = Depends(get_current_user_from_tenant)
):
    """Update a custom field"""
    field = db.query(CustomField).filter(
        and_(
            CustomField.id == field_id,
            CustomField.organization_id == current_user.organization_id
        )
    ).first()
    
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom field not found"
        )
    
    # Update only provided fields
    update_data = field_data.dict(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(field, field_name, value)
    
    db.commit()
    db.refresh(field)
    
    return field

@router.delete("/{field_id}")
async def delete_custom_field(
    field_id: str,
    db: Session = Depends(get_current_tenant_db),
    current_user: User = Depends(get_current_user_from_tenant)
):
    """Delete a custom field and all its values"""
    field = db.query(CustomField).filter(
        and_(
            CustomField.id == field_id,
            CustomField.organization_id == current_user.organization_id
        )
    ).first()
    
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom field not found"
        )
    
    # Delete all values for this field first
    db.query(CustomFieldValue).filter(
        CustomFieldValue.custom_field_id == field_id
    ).delete()
    
    # Delete the field definition
    db.delete(field)
    db.commit()
    
    return {"message": "Custom field deleted successfully"}

# Custom Field Values endpoints
@router.get("/values/{entity_type}/{entity_id}", response_model=EntityCustomFields)
async def get_entity_custom_field_values(
    entity_type: CustomFieldEntity,
    entity_id: str,
    db: Session = Depends(get_current_tenant_db),
    current_user: User = Depends(get_current_user_from_tenant)
):
    """Get all custom field values for a specific entity"""
    # Get all active custom fields for this entity type
    fields = db.query(CustomField).filter(
        and_(
            CustomField.organization_id == current_user.organization_id,
            CustomField.entity_type == entity_type,
            CustomField.is_active == True
        )
    ).all()
    
    # Get all values for this entity
    values = db.query(CustomFieldValue).filter(
        and_(
            CustomFieldValue.organization_id == current_user.organization_id,
            CustomFieldValue.entity_type == entity_type,
            CustomFieldValue.entity_id == entity_id
        )
    ).all()
    
    # Build a map of field values
    field_values = {}
    value_map = {v.custom_field_id: v.field_value for v in values}
    
    for field in fields:
        field_values[field.field_name] = value_map.get(str(field.id))
    
    return EntityCustomFields(
        entity_id=entity_id,
        entity_type=entity_type,
        values=field_values
    )

@router.post("/values", response_model=Dict[str, str])
async def set_entity_custom_field_values(
    entity_type: CustomFieldEntity,
    entity_id: str,
    field_values: Dict[str, Any],
    db: Session = Depends(get_current_tenant_db),
    current_user: User = Depends(get_current_user_from_tenant)
):
    """Set custom field values for an entity"""
    # Get all custom fields for this entity type
    fields = db.query(CustomField).filter(
        and_(
            CustomField.organization_id == current_user.organization_id,
            CustomField.entity_type == entity_type,
            CustomField.is_active == True
        )
    ).all()
    
    field_map = {f.field_name: f for f in fields}
    
    updated_fields = []
    
    for field_name, field_value in field_values.items():
        if field_name not in field_map:
            continue  # Skip unknown fields
            
        field = field_map[field_name]
        
        # Check if value already exists
        existing_value = db.query(CustomFieldValue).filter(
            and_(
                CustomFieldValue.custom_field_id == field.id,
                CustomFieldValue.entity_id == entity_id
            )
        ).first()
        
        if existing_value:
            # Update existing value
            existing_value.field_value = field_value
        else:
            # Create new value
            new_value = CustomFieldValue(
                organization_id=current_user.organization_id,
                custom_field_id=field.id,
                entity_type=entity_type,
                entity_id=entity_id,
                field_value=field_value
            )
            db.add(new_value)
        
        updated_fields.append(field_name)
    
    db.commit()
    
    return {"message": f"Updated {len(updated_fields)} custom field values", "updated_fields": updated_fields}