"""
Multi-tenant middleware for handling subdomain and path-based tenant routing
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import re
from typing import Optional

from ..db.database import AsyncSessionLocal
from ..models.organization import Organization


class TenantMiddleware:
    """Middleware to identify and set tenant context from request"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # Skip tenant detection for certain paths
            if self._should_skip_tenant_detection(request.url.path):
                await self.app(scope, receive, send)
                return
            
            # Detect tenant from URL
            tenant_info = await self._detect_tenant(request)
            
            # Add tenant info to request state
            if tenant_info:
                scope["state"]["tenant_id"] = tenant_info["id"]
                scope["state"]["tenant_slug"] = tenant_info["slug"]
                scope["state"]["tenant_type"] = tenant_info["type"]  # 'admin' or 'tenant'
            
        await self.app(scope, receive, send)
    
    def _should_skip_tenant_detection(self, path: str) -> bool:
        """Check if tenant detection should be skipped for this path"""
        skip_paths = [
            "/api/v1/docs",
            "/api/v1/redoc", 
            "/api/v1/openapi.json",
            "/health",
            "/favicon.ico",
            "/api/v1/analytics/shared/project/"  # Public shared project endpoints
        ]
        
        return any(path.startswith(skip_path) for skip_path in skip_paths)
    
    async def _detect_tenant(self, request: Request) -> Optional[dict]:
        """
        Detect tenant from URL patterns:
        - domain.com/admin -> admin context
        - domain.com/tenant-slug -> tenant context  
        - tenant-slug.domain.com -> tenant context (subdomain)
        - X-Tenant-Type header from frontend
        """
        host = request.headers.get("host", "")
        path = request.url.path
        
        # Pattern 0: Check headers from frontend (highest priority)
        tenant_type_header = request.headers.get("X-Tenant-Type", "").lower()
        tenant_slug_header = request.headers.get("X-Tenant-Slug", "")
        tenant_id_header = request.headers.get("X-Tenant-Id", "")
        
        if tenant_type_header == "admin":
            return {
                "id": tenant_id_header or "admin",
                "slug": tenant_slug_header or "admin",
                "type": "admin"
            }
        elif tenant_type_header == "tenant" and tenant_slug_header:
            return {
                "id": tenant_id_header or tenant_slug_header,
                "slug": tenant_slug_header,
                "type": "tenant"
            }
        
        # Pattern 1: Path-based routing (/admin or /tenant-slug)
        if path.startswith("/admin"):
            return {
                "id": "admin",
                "slug": "admin", 
                "type": "admin"
            }
        
        # Pattern 2: Path-based tenant routing (/api/v1/...)
        # Check if we have a tenant context from user authentication later
        # For now, we'll let the dependency injection handle this
        
        # Pattern 3: Subdomain-based routing (tenant-slug.domain.com)
        subdomain = self._extract_subdomain(host)
        if subdomain and subdomain != "www" and subdomain != "admin":
            # Validate if subdomain corresponds to a real tenant
            tenant_org = await self._get_organization_by_slug(subdomain)
            if tenant_org:
                return {
                    "id": tenant_org.id,
                    "slug": tenant_org.slug,
                    "type": "tenant"
                }
        
        # Pattern 4: Admin subdomain (admin.domain.com)
        if subdomain == "admin":
            return {
                "id": "admin",
                "slug": "admin",
                "type": "admin" 
            }
        
        return None
    
    def _extract_subdomain(self, host: str) -> Optional[str]:
        """Extract subdomain from host header"""
        if not host:
            return None
            
        # Remove port if present
        host = host.split(":")[0]
        
        # Split by dots
        parts = host.split(".")
        
        # Need at least 2 parts for a subdomain (subdomain.domain.com)
        if len(parts) >= 3:
            return parts[0]
        
        # localhost or single domain
        return None
    
    async def _get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by slug from database"""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Organization).where(
                        Organization.slug == slug,
                        Organization.is_active == True
                    )
                )
                return result.scalar_one_or_none()
        except Exception:
            return None


def get_tenant_context(request: Request) -> dict:
    """Get tenant context from request state"""
    return {
        "tenant_id": getattr(request.state, "tenant_id", None),
        "tenant_slug": getattr(request.state, "tenant_slug", None), 
        "tenant_type": getattr(request.state, "tenant_type", None)
    }


def is_admin_context(request: Request) -> bool:
    """Check if request is in admin context"""
    return getattr(request.state, "tenant_type", None) == "admin"


def is_tenant_context(request: Request) -> bool:
    """Check if request is in tenant context"""
    return getattr(request.state, "tenant_type", None) == "tenant"


def require_admin_context(request: Request):
    """Require admin context, raise exception otherwise"""
    if not is_admin_context(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin context required"
        )


def require_tenant_context(request: Request):
    """Require tenant context, raise exception otherwise"""
    tenant_type = getattr(request.state, "tenant_type", None)
    if tenant_type not in ["admin", "tenant"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context required"
        )

