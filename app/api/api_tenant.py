"""
Tenant-specific API endpoints for project management
"""
from fastapi import APIRouter, Depends, Request
from .api_v1.endpoints import (
    auth, users, organizations, projects, tasks, teams, customers, 
    items, proposals, invoices, analytics, websockets, files, 
    notifications, automation, workspaces, milestones, recurring_tasks, 
    task_dependencies, project_comments, task_assignees, context_cards, 
    handoff_summaries, decision_logs, knowledge_base, user_dashboard,
    scope_management, estimation, integration_hub, executive_reporting,
    smart_notifications, enhanced_handoff_summaries, vendors, purchase_orders,
    delivery_notes, goals, subscriptions, customer_attachments, calendar, todo,
    chat, email
)
from .deps_tenant import (
    get_current_active_user_master, 
    get_current_organization_master,
    validate_tenant_access,
    get_tenant_db
)
from ..middleware.tenant_middleware import require_tenant_context

tenant_router = APIRouter()

# Tenant context dependency
async def tenant_context_required(request: Request):
    """Ensure request is in tenant context"""
    require_tenant_context(request)
    return request

# Common dependencies for tenant endpoints - simplified for now
tenant_dependencies = []

# Include tenant-specific endpoints
tenant_router.include_router(
    auth.router, 
    prefix="/auth", 
    tags=["authentication"]
)

tenant_router.include_router(
    users.router, 
    prefix="/users", 
    tags=["users"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    organizations.router, 
    prefix="/organizations", 
    tags=["organizations"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    projects.router, 
    prefix="/projects", 
    tags=["projects"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    tasks.router, 
    prefix="/tasks", 
    tags=["tasks"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    teams.router, 
    prefix="/teams", 
    tags=["teams"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    customers.router, 
    prefix="/customers", 
    tags=["customers"]
)

# Customer Attachments
tenant_router.include_router(
    customer_attachments.router,
    prefix="/customers",
    tags=["customer-attachments"]
)

tenant_router.include_router(
    items.router, 
    prefix="/items", 
    tags=["items"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    proposals.router, 
    prefix="/proposals", 
    tags=["proposals"]
)

tenant_router.include_router(
    invoices.router, 
    prefix="/invoices", 
    tags=["invoices"]
    # Removed tenant_dependencies for main database access
)

tenant_router.include_router(
    analytics.router, 
    prefix="/analytics", 
    tags=["analytics"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    websockets.router, 
    prefix="", 
    tags=["websockets"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    files.router, 
    prefix="/files", 
    tags=["files"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    notifications.router, 
    prefix="/notifications", 
    tags=["notifications"],
    dependencies=tenant_dependencies
)

# Smart Notifications (advanced list/filters)
tenant_router.include_router(
    smart_notifications.router,
    prefix="/smart-notifications",
    tags=["smart-notifications"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    automation.router, 
    prefix="/automation", 
    tags=["automation"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    workspaces.router, 
    prefix="/workspaces", 
    tags=["workspaces"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    milestones.router, 
    prefix="/milestones", 
    tags=["milestones"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    recurring_tasks.router, 
    prefix="/recurring-tasks", 
    tags=["recurring-tasks"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    task_dependencies.router, 
    prefix="/task-dependencies", 
    tags=["task-dependencies"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    project_comments.router, 
    prefix="", 
    tags=["project-comments"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    task_assignees.router, 
    prefix="/task-assignees", 
    tags=["task-assignees"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    context_cards.router, 
    prefix="/context-cards", 
    tags=["context-cards"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    handoff_summaries.router, 
    prefix="/handoff-summaries", 
    tags=["handoff-summaries"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    decision_logs.router, 
    prefix="/decision-logs", 
    tags=["decision-logs"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    knowledge_base.router, 
    prefix="/knowledge-base", 
    tags=["knowledge-base"],
    dependencies=tenant_dependencies
)

# Add compatibility route for frontend
tenant_router.include_router(
    knowledge_base.router, 
    prefix="/knowledge", 
    tags=["knowledge"],
    dependencies=tenant_dependencies
)

# Knowledge Integration (suggestions and auto-linking)
from .api_v1.endpoints import knowledge_integration
tenant_router.include_router(
    knowledge_integration.router,
    prefix="/knowledge-integration",
    tags=["knowledge-integration"],
    dependencies=tenant_dependencies
)

# Advanced PM Features
tenant_router.include_router(
    user_dashboard.router, 
    prefix="/dashboard", 
    tags=["dashboard"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    scope_management.router, 
    prefix="", 
    tags=["scope-management"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    estimation.router, 
    prefix="", 
    tags=["estimation"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    integration_hub.router, 
    prefix="", 
    tags=["integration-hub"],
    dependencies=tenant_dependencies
)

# Email (SMTP) configuration for tenant
tenant_router.include_router(
    email.router,
    prefix="",
    tags=["email"],
    dependencies=tenant_dependencies
)

# Organization Chat endpoints
tenant_router.include_router(
    chat.router,
    prefix="",
    tags=["chat"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    executive_reporting.router, 
    prefix="", 
    tags=["executive-reporting"],
    dependencies=tenant_dependencies
)

# Enhanced Knowledge & Smart Notifications
tenant_router.include_router(
    smart_notifications.router, 
    prefix="/smart-notifications", 
    tags=["smart-notifications"],
    dependencies=tenant_dependencies
)

tenant_router.include_router(
    enhanced_handoff_summaries.router, 
    prefix="/enhanced-handoff-summaries", 
    tags=["enhanced-handoff-summaries"],
    dependencies=tenant_dependencies
)

# Purchase Management
tenant_router.include_router(
    vendors.router, 
    prefix="/vendors", 
    tags=["vendors"]
    # Temporarily removed tenant_dependencies to fix creation issue
)

tenant_router.include_router(
    purchase_orders.router, 
    prefix="/purchase-orders", 
    tags=["purchase-orders"]
    # Temporarily removed tenant_dependencies to fix creation issue
)

# Delivery Management
tenant_router.include_router(
    delivery_notes.router, 
    prefix="/delivery-notes", 
    tags=["delivery-notes"],
    dependencies=tenant_dependencies
)

# Goals Management
tenant_router.include_router(
    goals.router, 
    prefix="/goals", 
    tags=["goals"],
    dependencies=tenant_dependencies
)

# Calendar
tenant_router.include_router(
    calendar.router,
    prefix="/calendar",
    tags=["calendar"]
)

# To‑Do (Notes + Todos)
tenant_router.include_router(
    todo.router,
    prefix="/todo",
    tags=["todo"],
)

# Subscriptions
tenant_router.include_router(
    subscriptions.router,
    prefix="/subscriptions",
    tags=["subscriptions"],
    dependencies=tenant_dependencies
)

# Billing
from .api_v1.endpoints import billing as billing_endpoints
tenant_router.include_router(
    billing_endpoints.router,
    prefix="/billing",
    tags=["billing"]
)

# AI Module
from .api_v1.endpoints import ai
tenant_router.include_router(
    ai.router,
    prefix="/ai",
    tags=["ai"],
    dependencies=tenant_dependencies
)


