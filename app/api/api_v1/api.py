from fastapi import APIRouter, Request, Depends
from ..api_admin import admin_router
from ..api_tenant import tenant_router
from ...middleware.tenant_middleware import get_tenant_context

api_router = APIRouter()

async def route_by_context(request: Request):
    """Route requests based on tenant context"""
    tenant_context = get_tenant_context(request)
    
    # Route to appropriate sub-router based on context
    # if tenant_context["tenant_type"] == "admin":
    #     return admin_router
    if tenant_context["tenant_type"] == "tenant":
        return tenant_router
    else:
        # Default to tenant router for backward compatibility
        return tenant_router

# Include context-aware routing
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(tenant_router, prefix="", tags=["tenant"])
