"""Unified Integration Hub API endpoints"""
from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from ....api.deps_tenant import get_current_active_user_master as get_current_active_user, get_tenant_db
from ....models.user import User
from ....models.integration_hub import (
    Integration, IntegrationSyncLog, UniversalSearch, ActivityStream,
    SmartConnector, QuickAction
)
from ....schemas.integration_hub import (
    Integration as IntegrationSchema, IntegrationCreate, IntegrationUpdate,
    IntegrationSyncLog as IntegrationSyncLogSchema, IntegrationSyncLogCreate,
    UniversalSearch as UniversalSearchSchema, UniversalSearchCreate,
    ActivityStream as ActivityStreamSchema, ActivityStreamCreate,
    SmartConnector as SmartConnectorSchema, SmartConnectorCreate, SmartConnectorUpdate,
    QuickAction as QuickActionSchema, QuickActionCreate, QuickActionUpdate,
    SearchResult, ActivityFeed
)

router = APIRouter()


# Integration Management Endpoints
@router.get("/integrations", response_model=List[IntegrationSchema])
async def get_integrations(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    integration_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Get user's integrations"""
    stmt = select(Integration).where(
        Integration.organization_id == current_user.organization_id
    )
    
    if integration_type:
        stmt = stmt.where(Integration.integration_type == integration_type)
    
    if is_active is not None:
        stmt = stmt.where(Integration.is_active == is_active)
    
    stmt = stmt.order_by(Integration.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    integrations = result.scalars().all()
    
    return integrations


@router.post("/integrations", response_model=IntegrationSchema)
async def create_integration(
    integration_data: IntegrationCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new integration"""
    # Validate integration config
    if not validate_integration_config(integration_data.integration_type, integration_data.config):
        raise HTTPException(status_code=400, detail="Invalid integration configuration")
    
    integration = Integration(
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
        **integration_data.dict()
    )
    
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    
    # Start initial sync in background
    background_tasks.add_task(perform_initial_sync, integration.id, db)
    
    return integration


@router.get("/integrations/{integration_id}", response_model=IntegrationSchema)
async def get_integration(
    integration_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific integration"""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    return integration


@router.put("/integrations/{integration_id}", response_model=IntegrationSchema)
async def update_integration(
    integration_id: str,
    integration_data: IntegrationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update an integration"""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    for field, value in integration_data.dict(exclude_unset=True).items():
        setattr(integration, field, value)
    
    integration.last_modified_by_id = current_user.id
    
    await db.commit()
    await db.refresh(integration)
    
    return integration


@router.post("/integrations/{integration_id}/sync")
async def trigger_sync(
    integration_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Trigger manual sync for an integration"""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    if not integration.is_active:
        raise HTTPException(status_code=400, detail="Integration is not active")
    
    # Trigger sync in background
    background_tasks.add_task(perform_sync, integration_id, current_user.id, db)
    
    return {"message": "Sync triggered successfully"}


@router.get("/integrations/{integration_id}/status")
async def get_integration_status(
    integration_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get integration status and health"""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    # Get recent sync logs
    sync_stmt = select(IntegrationSyncLog).where(
        IntegrationSyncLog.integration_id == integration_id
    ).order_by(IntegrationSyncLog.sync_started_at.desc()).limit(5)
    
    sync_result = await db.execute(sync_stmt)
    recent_syncs = sync_result.scalars().all()
    
    # Calculate health metrics
    status_data = calculate_integration_health(integration, recent_syncs)
    
    return {
        "integration_id": integration_id,
        "is_connected": integration.is_active and status_data['is_connected'],
        "last_sync": integration.last_sync_at,
        "sync_frequency": integration.sync_frequency,
        "health_score": status_data['health_score'],
        "error_count": status_data['error_count'],
        "success_rate": status_data['success_rate'],
        "recent_syncs": [{
            'id': sync.id,
            'status': sync.status,
            'started_at': sync.sync_started_at.isoformat(),
            'completed_at': sync.sync_completed_at.isoformat() if sync.sync_completed_at else None,
            'records_processed': sync.records_processed or 0,
            'errors': sync.errors or []
        } for sync in recent_syncs]
    }


# Universal Search Endpoints
@router.get("/search", response_model=SearchResult)
async def universal_search(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    sources: Optional[List[str]] = Query(None),
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Perform universal search across all integrated tools"""
    if len(q.strip()) < 1:
        raise HTTPException(status_code=400, detail="Search query too short")
    
    # Get user's active integrations
    integrations_stmt = select(Integration).where(
        Integration.organization_id == current_user.organization_id,
        Integration.is_active == True
    )
    
    if sources:
        integrations_stmt = integrations_stmt.where(Integration.integration_type.in_(sources))
    
    integrations_result = await db.execute(integrations_stmt)
    active_integrations = integrations_result.scalars().all()
    
    # Perform search across integrated sources
    search_results = await perform_universal_search(q, active_integrations, limit, offset)
    
    # Log search for analytics
    search_log = UniversalSearch(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        query=q,
        sources_searched=[i.integration_type for i in active_integrations],
        results_count=len(search_results['results']),
        response_time_ms=search_results['response_time_ms']
    )
    db.add(search_log)
    await db.commit()
    
    return SearchResult(
        query=q,
        total_results=search_results['total'],
        sources_searched=search_results['sources'],
        response_time_ms=search_results['response_time_ms'],
        results=search_results['results']
    )


@router.get("/search/suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    limit: int = Query(default=5, le=10),
) -> Any:
    """Get search suggestions based on query"""
    suggestions = await generate_search_suggestions(q, current_user.organization_id, limit, db)
    
    return {"suggestions": suggestions}


# Activity Stream Endpoints
@router.get("/activity", response_model=ActivityFeed)
async def get_activity_stream(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    source: Optional[str] = Query(None),
    activity_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Get consolidated activity stream"""
    stmt = select(ActivityStream).where(
        ActivityStream.organization_id == current_user.organization_id
    )
    
    if source:
        stmt = stmt.where(ActivityStream.source == source)
    
    if activity_type:
        stmt = stmt.where(ActivityStream.activity_type == activity_type)
    
    if user_id:
        stmt = stmt.where(ActivityStream.user_id == user_id)
    
    stmt = stmt.order_by(ActivityStream.activity_timestamp.desc()).offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    activities = result.scalars().all()
    
    # Get activity sources summary
    sources_stmt = select(
        ActivityStream.source,
        func.count(ActivityStream.id).label('count')
    ).where(
        ActivityStream.organization_id == current_user.organization_id
    ).group_by(ActivityStream.source)
    
    sources_result = await db.execute(sources_stmt)
    sources_summary = {row.source: row.count for row in sources_result}
    
    return ActivityFeed(
        activities=[{
            'id': activity.id,
            'source': activity.source,
            'activity_type': activity.activity_type,
            'title': activity.title,
            'description': activity.description,
            'user_id': activity.user_id,
            'metadata': activity.metadata,
            'activity_timestamp': activity.activity_timestamp.isoformat(),
            'external_url': activity.external_url
        } for activity in activities],
        sources_summary=sources_summary,
        total_count=len(activities)
    )


@router.post("/activity", response_model=ActivityStreamSchema)
async def create_activity(
    activity_data: ActivityStreamCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new activity entry"""
    activity = ActivityStream(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        **activity_data.dict()
    )
    
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    
    return activity


# Smart Connectors Endpoints
@router.get("/connectors", response_model=List[SmartConnectorSchema])
async def get_smart_connectors(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    connector_type: Optional[str] = Query(None),
    is_enabled: Optional[bool] = Query(None),
) -> Any:
    """Get available smart connectors"""
    stmt = select(SmartConnector).where(
        SmartConnector.organization_id == current_user.organization_id
    )
    
    if connector_type:
        stmt = stmt.where(SmartConnector.connector_type == connector_type)
    
    if is_enabled is not None:
        stmt = stmt.where(SmartConnector.is_enabled == is_enabled)
    
    stmt = stmt.order_by(SmartConnector.priority.desc())
    
    result = await db.execute(stmt)
    connectors = result.scalars().all()
    
    return connectors


@router.post("/connectors", response_model=SmartConnectorSchema)
async def create_smart_connector(
    connector_data: SmartConnectorCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new smart connector"""
    connector = SmartConnector(
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
        **connector_data.dict()
    )
    
    db.add(connector)
    await db.commit()
    await db.refresh(connector)
    
    return connector


@router.put("/connectors/{connector_id}", response_model=SmartConnectorSchema)
async def update_smart_connector(
    connector_id: str,
    connector_data: SmartConnectorUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a smart connector"""
    stmt = select(SmartConnector).where(
        SmartConnector.id == connector_id,
        SmartConnector.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    connector = result.scalar_one_or_none()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    for field, value in connector_data.dict(exclude_unset=True).items():
        setattr(connector, field, value)
    
    await db.commit()
    await db.refresh(connector)
    
    return connector


# Quick Actions Endpoints
@router.get("/quick-actions", response_model=List[QuickActionSchema])
async def get_quick_actions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    context: Optional[str] = Query(None),
    is_enabled: bool = Query(default=True),
) -> Any:
    """Get available quick actions for current context"""
    stmt = select(QuickAction).where(
        QuickAction.organization_id == current_user.organization_id,
        QuickAction.is_enabled == is_enabled
    )
    
    if context:
        stmt = stmt.where(or_(
            QuickAction.context_filters.contains({context: True}),
            QuickAction.context_filters == {}
        ))
    
    stmt = stmt.order_by(QuickAction.priority.desc())
    
    result = await db.execute(stmt)
    actions = result.scalars().all()
    
    return actions


@router.post("/quick-actions", response_model=QuickActionSchema)
async def create_quick_action(
    action_data: QuickActionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new quick action"""
    action = QuickAction(
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
        **action_data.dict()
    )
    
    db.add(action)
    await db.commit()
    await db.refresh(action)
    
    return action


@router.post("/quick-actions/{action_id}/execute")
async def execute_quick_action(
    action_id: str,
    action_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Execute a quick action"""
    stmt = select(QuickAction).where(
        QuickAction.id == action_id,
        QuickAction.organization_id == current_user.organization_id,
        QuickAction.is_enabled == True
    )
    result = await db.execute(stmt)
    action = result.scalar_one_or_none()
    
    if not action:
        raise HTTPException(status_code=404, detail="Action not found or disabled")
    
    # Execute action in background
    background_tasks.add_task(execute_action, action, action_data, current_user.id, db)
    
    # Update usage count
    action.usage_count += 1
    action.last_used_at = func.now()
    await db.commit()
    
    return {"message": "Action execution started", "action_id": action_id}


# Helper Functions
def validate_integration_config(integration_type: str, config: Dict[str, Any]) -> bool:
    """Validate integration configuration"""
    required_fields = {
        'slack': ['bot_token', 'workspace_id'],
        'github': ['access_token', 'repository'],
        'gmail': ['refresh_token', 'client_id'],
        'jira': ['api_token', 'instance_url'],
        'trello': ['api_key', 'token'],
        'asana': ['access_token'],
        'notion': ['api_token']
    }
    
    if integration_type not in required_fields:
        return False
    
    required = required_fields[integration_type]
    return all(field in config for field in required)


async def perform_initial_sync(integration_id: str, db: AsyncSession):
    """Perform initial sync for a new integration"""
    # Implementation would depend on integration type
    pass


async def perform_sync(integration_id: str, user_id: str, db: AsyncSession):
    """Perform sync for an integration"""
    # Implementation would depend on integration type
    pass


def calculate_integration_health(integration: Integration, recent_syncs: List[IntegrationSyncLog]) -> Dict[str, Any]:
    """Calculate integration health metrics"""
    if not recent_syncs:
        return {
            'is_connected': False,
            'health_score': 0,
            'error_count': 0,
            'success_rate': 0
        }
    
    successful_syncs = [s for s in recent_syncs if s.status == 'completed']
    error_count = len([s for s in recent_syncs if s.status == 'failed'])
    success_rate = len(successful_syncs) / len(recent_syncs) * 100
    
    # Simple health scoring
    health_score = max(0, 100 - (error_count * 20))
    
    return {
        'is_connected': recent_syncs[0].status != 'failed',
        'health_score': health_score,
        'error_count': error_count,
        'success_rate': success_rate
    }


async def perform_universal_search(query: str, integrations: List[Integration], limit: int, offset: int) -> Dict[str, Any]:
    """Perform search across integrated tools"""
    # Simulate search results - in real implementation, this would call actual APIs
    results = []
    sources = []
    
    for integration in integrations:
        sources.append(integration.integration_type)
        
        # Simulate results from each integration
        if integration.integration_type == 'slack':
            results.extend([
                {
                    'id': f'slack_{i}',
                    'title': f'Slack message containing "{query}"',
                    'content': f'Message content with {query}...',
                    'source': 'slack',
                    'type': 'message',
                    'url': f'https://workspace.slack.com/archives/C123/{i}',
                    'timestamp': '2024-01-15T10:30:00Z',
                    'author': 'John Doe'
                } for i in range(2)
            ])
        
        elif integration.integration_type == 'github':
            results.extend([
                {
                    'id': f'github_{i}',
                    'title': f'PR #{i+1}: Fix {query} issue',
                    'content': f'Pull request addressing {query}...',
                    'source': 'github',
                    'type': 'pull_request',
                    'url': f'https://github.com/org/repo/pull/{i+1}',
                    'timestamp': '2024-01-14T15:45:00Z',
                    'author': 'jane-dev'
                } for i in range(1)
            ])
    
    # Apply pagination
    paginated_results = results[offset:offset + limit]
    
    return {
        'results': paginated_results,
        'total': len(results),
        'sources': sources,
        'response_time_ms': 150
    }


async def generate_search_suggestions(query: str, org_id: str, limit: int, db: AsyncSession) -> List[str]:
    """Generate search suggestions based on query and history"""
    # Simulate suggestions - in real implementation, use ML/analytics
    base_suggestions = [
        f"{query} in slack",
        f"{query} in github",
        f"{query} issues",
        f"{query} documentation",
        f"{query} recent"
    ]
    
    return base_suggestions[:limit]


async def execute_action(action: QuickAction, action_data: Dict[str, Any], user_id: str, db: AsyncSession):
    """Execute a quick action"""
    # Implementation would depend on action type
    pass
