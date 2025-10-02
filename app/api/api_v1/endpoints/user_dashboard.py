"""User Dashboard API endpoints"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ....api.deps_tenant import get_current_active_user_master as get_current_active_user, get_tenant_db
from ....models.user import User
from ....models.user_dashboard import (
    UserDashboardPreference, DashboardWidget, CustomField, 
    WorkflowTemplate, UserWorkflowPreference
)
from ....schemas.user_dashboard import (
    DashboardPreferences, DashboardPreferencesCreate, DashboardPreferencesUpdate,
    DashboardWidget as DashboardWidgetSchema, DashboardWidgetCreate, DashboardWidgetUpdate,
    CustomField as CustomFieldSchema, CustomFieldCreate, CustomFieldUpdate,
    WorkflowTemplate as WorkflowTemplateSchema, WorkflowTemplateCreate, WorkflowTemplateUpdate,
    UserWorkflowPreferences, UserWorkflowPreferencesCreate, UserWorkflowPreferencesUpdate,
    DashboardSummary, WidgetData
)

router = APIRouter()


# Dashboard Preferences Endpoints
@router.get("/preferences", response_model=DashboardPreferences)
async def get_dashboard_preferences(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get current user's dashboard preferences"""
    stmt = select(UserDashboardPreference).where(
        UserDashboardPreference.user_id == current_user.id
    )
    result = await db.execute(stmt)
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        # Create default preferences
        preferences = UserDashboardPreference(
            user_id=current_user.id,
            enabled_widgets=["project_status", "my_tasks", "upcoming_deadlines", "recent_activity"],
            widget_positions={},
            widget_settings={}
        )
        db.add(preferences)
        await db.commit()
        await db.refresh(preferences)
    
    return preferences


@router.post("/preferences", response_model=DashboardPreferences)
async def create_dashboard_preferences(
    preferences_data: DashboardPreferencesCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create or update dashboard preferences"""
    # Check if preferences already exist
    stmt = select(UserDashboardPreference).where(
        UserDashboardPreference.user_id == current_user.id
    )
    result = await db.execute(stmt)
    existing_preferences = result.scalar_one_or_none()
    
    if existing_preferences:
        # Update existing preferences
        for field, value in preferences_data.dict(exclude_unset=True).items():
            setattr(existing_preferences, field, value)
        
        await db.commit()
        await db.refresh(existing_preferences)
        return existing_preferences
    else:
        # Create new preferences
        preferences = UserDashboardPreference(
            user_id=current_user.id,
            **preferences_data.dict()
        )
        db.add(preferences)
        await db.commit()
        await db.refresh(preferences)
        return preferences


@router.put("/preferences", response_model=DashboardPreferences)
async def update_dashboard_preferences(
    preferences_data: DashboardPreferencesUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update dashboard preferences"""
    stmt = select(UserDashboardPreference).where(
        UserDashboardPreference.user_id == current_user.id
    )
    result = await db.execute(stmt)
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        raise HTTPException(status_code=404, detail="Dashboard preferences not found")
    
    for field, value in preferences_data.dict(exclude_unset=True).items():
        setattr(preferences, field, value)
    
    await db.commit()
    await db.refresh(preferences)
    return preferences


# Dashboard Widget Endpoints
@router.get("/widgets", response_model=List[DashboardWidgetSchema])
async def get_dashboard_widgets(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    widget_type: Optional[str] = Query(None),
    is_public: Optional[bool] = Query(None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Get available dashboard widgets"""
    stmt = select(DashboardWidget).where(
        DashboardWidget.organization_id == current_user.organization_id,
        DashboardWidget.is_active == True
    )
    
    if widget_type:
        stmt = stmt.where(DashboardWidget.widget_type == widget_type)
    
    if is_public is not None:
        stmt = stmt.where(DashboardWidget.is_public == is_public)
    
    # If not public, only show user's widgets or organization public widgets
    if is_public is False:
        stmt = stmt.where(DashboardWidget.created_by_id == current_user.id)
    
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    widgets = result.scalars().all()
    
    return widgets


@router.post("/widgets", response_model=DashboardWidgetSchema)
async def create_dashboard_widget(
    widget_data: DashboardWidgetCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new dashboard widget"""
    widget = DashboardWidget(
        created_by_id=current_user.id,
        organization_id=current_user.organization_id,
        **widget_data.dict()
    )
    
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


@router.get("/widgets/{widget_id}", response_model=DashboardWidgetSchema)
async def get_dashboard_widget(
    widget_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific dashboard widget"""
    stmt = select(DashboardWidget).where(
        DashboardWidget.id == widget_id,
        DashboardWidget.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    widget = result.scalar_one_or_none()
    
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")
    
    # Check permissions
    if not widget.is_public and widget.created_by_id != current_user.id:
        if current_user.role.value not in widget.allowed_roles:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return widget


@router.put("/widgets/{widget_id}", response_model=DashboardWidgetSchema)
async def update_dashboard_widget(
    widget_id: str,
    widget_data: DashboardWidgetUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a dashboard widget"""
    stmt = select(DashboardWidget).where(
        DashboardWidget.id == widget_id,
        DashboardWidget.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    widget = result.scalar_one_or_none()
    
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")
    
    # Check permissions
    if widget.created_by_id != current_user.id and current_user.role.value != "ADMIN":
        raise HTTPException(status_code=403, detail="Only widget creator or admin can update")
    
    for field, value in widget_data.dict(exclude_unset=True).items():
        setattr(widget, field, value)
    
    await db.commit()
    await db.refresh(widget)
    return widget


@router.delete("/widgets/{widget_id}")
async def delete_dashboard_widget(
    widget_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Delete a dashboard widget"""
    stmt = select(DashboardWidget).where(
        DashboardWidget.id == widget_id,
        DashboardWidget.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    widget = result.scalar_one_or_none()
    
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")
    
    # Check permissions
    if widget.created_by_id != current_user.id and current_user.role.value != "ADMIN":
        raise HTTPException(status_code=403, detail="Only widget creator or admin can delete")
    
    await db.delete(widget)
    await db.commit()
    return {"message": "Widget deleted successfully"}


# Custom Fields Endpoints
@router.get("/custom-fields", response_model=List[CustomFieldSchema])
async def get_custom_fields(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    applies_to: Optional[str] = Query(None),
    field_type: Optional[str] = Query(None),
    is_active: bool = Query(default=True),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Get custom fields for the organization"""
    stmt = select(CustomField).where(
        CustomField.organization_id == current_user.organization_id,
        CustomField.is_active == is_active
    )
    
    if applies_to:
        stmt = stmt.where(CustomField.applies_to.contains([applies_to]))
    
    if field_type:
        stmt = stmt.where(CustomField.field_type == field_type)
    
    stmt = stmt.order_by(CustomField.display_order, CustomField.name)
    stmt = stmt.offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    fields = result.scalars().all()
    
    return fields


@router.post("/custom-fields", response_model=CustomFieldSchema)
async def create_custom_field(
    field_data: CustomFieldCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new custom field"""
    # Check if field key already exists
    stmt = select(CustomField).where(
        CustomField.organization_id == current_user.organization_id,
        CustomField.field_key == field_data.field_key,
        CustomField.is_active == True
    )
    result = await db.execute(stmt)
    existing_field = result.scalar_one_or_none()
    
    if existing_field:
        raise HTTPException(
            status_code=400, 
            detail=f"Custom field with key '{field_data.field_key}' already exists"
        )
    
    field = CustomField(
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
        **field_data.dict()
    )
    
    db.add(field)
    await db.commit()
    await db.refresh(field)
    return field


@router.get("/custom-fields/{field_id}", response_model=CustomFieldSchema)
async def get_custom_field(
    field_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific custom field"""
    stmt = select(CustomField).where(
        CustomField.id == field_id,
        CustomField.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    field = result.scalar_one_or_none()
    
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    
    return field


@router.put("/custom-fields/{field_id}", response_model=CustomFieldSchema)
async def update_custom_field(
    field_id: str,
    field_data: CustomFieldUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a custom field"""
    stmt = select(CustomField).where(
        CustomField.id == field_id,
        CustomField.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    field = result.scalar_one_or_none()
    
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    
    # Only admin or field creator can update
    if field.created_by_id != current_user.id and current_user.role.value != "ADMIN":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    for attr, value in field_data.dict(exclude_unset=True).items():
        setattr(field, attr, value)
    
    await db.commit()
    await db.refresh(field)
    return field


@router.delete("/custom-fields/{field_id}")
async def delete_custom_field(
    field_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Delete a custom field (soft delete)"""
    stmt = select(CustomField).where(
        CustomField.id == field_id,
        CustomField.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    field = result.scalar_one_or_none()
    
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    
    # Only admin or field creator can delete
    if field.created_by_id != current_user.id and current_user.role.value != "ADMIN":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    field.is_active = False
    await db.commit()
    return {"message": "Custom field deleted successfully"}


# Workflow Templates Endpoints
@router.get("/workflow-templates", response_model=List[WorkflowTemplateSchema])
async def get_workflow_templates(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    category: Optional[str] = Query(None),
    is_public: Optional[bool] = Query(None),
    is_featured: Optional[bool] = Query(None),
    is_active: bool = Query(default=True),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Get workflow templates"""
    stmt = select(WorkflowTemplate).where(
        WorkflowTemplate.organization_id == current_user.organization_id,
        WorkflowTemplate.is_active == is_active
    )
    
    if category:
        stmt = stmt.where(WorkflowTemplate.category == category)
    
    if is_public is not None:
        stmt = stmt.where(WorkflowTemplate.is_public == is_public)
    
    if is_featured is not None:
        stmt = stmt.where(WorkflowTemplate.is_featured == is_featured)
    
    stmt = stmt.order_by(WorkflowTemplate.is_featured.desc(), WorkflowTemplate.usage_count.desc())
    stmt = stmt.offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    templates = result.scalars().all()
    
    return templates


@router.post("/workflow-templates", response_model=WorkflowTemplateSchema)
async def create_workflow_template(
    template_data: WorkflowTemplateCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new workflow template"""
    template = WorkflowTemplate(
        created_by_id=current_user.id,
        organization_id=current_user.organization_id,
        **template_data.dict()
    )
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/workflow-templates/{template_id}", response_model=WorkflowTemplateSchema)
async def get_workflow_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific workflow template"""
    stmt = select(WorkflowTemplate).where(
        WorkflowTemplate.id == template_id,
        WorkflowTemplate.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    
    return template


@router.put("/workflow-templates/{template_id}", response_model=WorkflowTemplateSchema)
async def update_workflow_template(
    template_id: str,
    template_data: WorkflowTemplateUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a workflow template"""
    stmt = select(WorkflowTemplate).where(
        WorkflowTemplate.id == template_id,
        WorkflowTemplate.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    
    # Only template creator or admin can update
    if template.created_by_id != current_user.id and current_user.role.value != "ADMIN":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    for field, value in template_data.dict(exclude_unset=True).items():
        setattr(template, field, value)
    
    await db.commit()
    await db.refresh(template)
    return template


# User Workflow Preferences Endpoints
@router.get("/workflow-preferences", response_model=UserWorkflowPreferences)
async def get_workflow_preferences(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get current user's workflow preferences"""
    stmt = select(UserWorkflowPreference).where(
        UserWorkflowPreference.user_id == current_user.id
    )
    result = await db.execute(stmt)
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        # Create default preferences
        preferences = UserWorkflowPreference(
            user_id=current_user.id,
            preferred_task_statuses=["todo", "in_progress", "review", "completed"],
            preferred_project_phases=["planning", "execution", "monitoring", "closure"]
        )
        db.add(preferences)
        await db.commit()
        await db.refresh(preferences)
    
    return preferences


@router.put("/workflow-preferences", response_model=UserWorkflowPreferences)
async def update_workflow_preferences(
    preferences_data: UserWorkflowPreferencesUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update workflow preferences"""
    stmt = select(UserWorkflowPreference).where(
        UserWorkflowPreference.user_id == current_user.id
    )
    result = await db.execute(stmt)
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        # Create if doesn't exist
        preferences = UserWorkflowPreference(
            user_id=current_user.id,
            **preferences_data.dict(exclude_unset=True)
        )
        db.add(preferences)
    else:
        # Update existing
        for field, value in preferences_data.dict(exclude_unset=True).items():
            setattr(preferences, field, value)
    
    await db.commit()
    await db.refresh(preferences)
    return preferences


# Dashboard Summary Endpoint
@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get dashboard summary data"""
    # This would typically aggregate data from projects, tasks, etc.
    # For now, return a basic structure
    
    summary_data = {
        "total_projects": 0,
        "active_projects": 0,
        "completed_projects": 0,
        "overdue_projects": 0,
        "total_tasks": 0,
        "my_tasks": 0,
        "completed_tasks": 0,
        "overdue_tasks": 0,
        "team_members": 0,
        "upcoming_deadlines": [],
        "recent_activity": []
    }
    
    return DashboardSummary(**summary_data)
