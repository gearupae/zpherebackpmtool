"""
Admin-specific API endpoints for platform administration
"""
from fastapi import APIRouter, Depends, Request
from .api_v1.endpoints import admin_analytics, admin_tenants  # admin_modules temporarily disabled
from .deps_tenant import require_platform_admin_master
from ..middleware.tenant_middleware import require_admin_context

admin_router = APIRouter()

# Admin context dependency
async def admin_context_required(request: Request):
    """Ensure request is in admin context"""
    require_admin_context(request)
    return request

# Include admin-only endpoints
admin_router.include_router(
    admin_analytics.router, 
    prefix="/analytics", 
    tags=["admin-analytics"],
    dependencies=[Depends(admin_context_required), Depends(require_platform_admin_master)]
)

admin_router.include_router(
    admin_tenants.router, 
    prefix="/tenants", 
    tags=["tenant-management"],
    dependencies=[Depends(admin_context_required), Depends(require_platform_admin_master)]
)

# admin_router.include_router(
#     admin_modules.router, 
#     prefix="/modules", 
#     tags=["module-management"],
#     dependencies=[Depends(admin_context_required), Depends(require_platform_admin_master)]
# )
# admin_router.include_router(billing_management.router, prefix="/billing", tags=["billing-management"])

