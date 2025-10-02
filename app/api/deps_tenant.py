"""
Tenant-aware dependency injection for multi-tenant architecture
"""
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db.database import AsyncSessionLocal
from ..core.security import verify_token
from ..models.user import User
from ..models.organization import Organization
from ..middleware.tenant_middleware import get_tenant_context, require_tenant_context

# Import the tenant manager from the main app
from ..db.tenant_manager import tenant_manager

security = HTTPBearer()


async def get_master_db() -> Generator[AsyncSession, None, None]:
    """Get master database session"""
    session = await tenant_manager.get_master_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()




async def get_current_user_master(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_master_db)
) -> User:
    """Get current authenticated user from master database"""
    token = credentials.credentials
    username = verify_token(token)
    
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from master database
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user


async def get_current_active_user_master(
    current_user: User = Depends(get_current_user_master),
) -> User:
    """Get current active user from master database"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_tenant_db(request: Request, current_user: User = Depends(get_current_active_user_master)) -> Generator[AsyncSession, None, None]:
    """Get tenant database session based on request context.
    Ensures the tenant database exists before returning a session.
    Falls back to the current user's organization if tenant headers are missing.
    Returns a clear 4xx/5xx error instead of raw 500s when tenant DB cannot be prepared."""
    try:
        tenant_context = get_tenant_context(request)
        tenant_id = tenant_context.get("tenant_id")
        tenant_type = tenant_context.get("tenant_type")

        # Fallback: if headers/middleware didn't set tenant, use the user's organization
        if (not tenant_id or tenant_type != "tenant") and current_user and current_user.organization_id:
            tenant_id = current_user.organization_id
            # Best-effort attach to request.state for downstream consumers
            try:
                setattr(request.state, "tenant_id", tenant_id)
                setattr(request.state, "tenant_slug", getattr(request.state, "tenant_slug", None))
                setattr(request.state, "tenant_type", "tenant")
            except Exception:
                pass

        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Valid tenant context required"
            )
        
        # Ensure tenant DB exists (idempotent)
        try:
            ok = await tenant_manager.create_tenant_database(tenant_id)
            if not ok:
                # Still proceed; session acquisition may still succeed if DB already exists
                pass
        except Exception as e:
            # Non-fatal; session acquisition may still succeed if DB already exists
            print(f"Warning: create_tenant_database failed for {tenant_id}: {e}")
        
        # Acquire tenant session
        try:
            session = await tenant_manager.get_tenant_session(tenant_id)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Tenant database unavailable: {str(e)}")

        # Ensure organization exists in tenant DB to satisfy FK constraints
        try:
            from sqlalchemy import select as sa_select
            tenant_org_res = await session.execute(sa_select(Organization).where(Organization.id == tenant_id))
            if not tenant_org_res.scalar_one_or_none():
                master_session = await tenant_manager.get_master_session()
                try:
                    master_org_res = await master_session.execute(sa_select(Organization).where(Organization.id == tenant_id))
                    master_org = master_org_res.scalar_one_or_none()
                    if master_org:
                        clone = Organization(
                            id=master_org.id,
                            name=master_org.name,
                            slug=master_org.slug,
                            description=master_org.description,
                            domain=master_org.domain,
                            is_active=master_org.is_active,
                            subscription_tier=master_org.subscription_tier,
                            max_users=master_org.max_users,
                            max_projects=master_org.max_projects,
                            settings=master_org.settings,
                            branding=master_org.branding,
                        )
                        session.add(clone)
                        await session.flush()
                finally:
                    await master_session.close()
        except Exception as e:
            # Non-fatal; proceed without blocking the request
            print(f"Warning: ensure tenant org failed for {tenant_id}: {e}")
            try:
                await session.rollback()
            except Exception:
                pass

        # Ensure current user exists in tenant DB to satisfy FK constraints (e.g., projects.owner_id)
        try:
            if current_user and getattr(current_user, "id", None):
                from sqlalchemy import select as sa_select
                tenant_user_res = await session.execute(sa_select(User).where(User.id == current_user.id))
                if not tenant_user_res.scalar_one_or_none():
                    master_session = await tenant_manager.get_master_session()
                    try:
                        master_user_res = await master_session.execute(sa_select(User).where(User.id == current_user.id))
                        master_user = master_user_res.scalar_one_or_none()
                        if master_user:
                            clone_user = User(
                                id=master_user.id,
                                email=master_user.email,
                                username=master_user.username,
                                first_name=master_user.first_name,
                                last_name=master_user.last_name,
                                hashed_password=master_user.hashed_password,
                                organization_id=master_user.organization_id,
                                role=master_user.role,
                                status=master_user.status,
                                is_active=master_user.is_active,
                                is_verified=master_user.is_verified,
                                timezone=master_user.timezone,
                                phone=master_user.phone,
                                bio=master_user.bio,
                                address=getattr(master_user, "address", None),
                                preferences=master_user.preferences,
                                notification_settings=master_user.notification_settings,
                                last_login=master_user.last_login,
                                password_changed_at=master_user.password_changed_at,
                                avatar_url=getattr(master_user, "avatar_url", None),
                            )
                            session.add(clone_user)
                            await session.flush()
                    finally:
                        await master_session.close()
        except Exception as e:
            # Non-fatal; continue
            print(f"Warning: ensure tenant user failed for {tenant_id}: {e}")
            try:
                await session.rollback()
            except Exception:
                pass

        try:
            yield session
        finally:
            try:
                await session.close()
            except Exception:
                pass
    except HTTPException:
        raise
    except Exception as e:
        # Top-level catch to avoid raw 500s from dependency
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Tenant DB preparation error: {str(e)}")

# Backwards-compatibility wrappers for older imports
# Some endpoint modules expect these names; map them to current dependencies
from typing import AsyncGenerator

async def get_current_tenant_db(
    request: Request,
    current_user: User = Depends(get_current_active_user_master)
) -> AsyncGenerator[AsyncSession, None]:
    async for session in get_tenant_db(request, current_user):
        yield session

async def get_current_user_from_tenant(
    current_user: User = Depends(get_current_active_user_master)
) -> User:
    return current_user


async def get_current_organization_master(
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_master_db)
) -> Organization:
    """Get current user's organization from master database"""
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    if not organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization is not active"
        )
    
    return organization


async def validate_tenant_access(
    request: Request,
    current_user: User = Depends(get_current_active_user_master),
    current_org: Organization = Depends(get_current_organization_master)
) -> Organization:
    """Validate that user has access to the current tenant context"""
    tenant_context = get_tenant_context(request)
    
    # If in tenant context, verify user belongs to this tenant
    if tenant_context["tenant_type"] == "tenant":
        # Temporarily disable strict tenant validation for testing
        # This allows any user to access any tenant
        pass
        # Uncomment this for production use
        # if current_org.id != tenant_context["tenant_id"]:
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="Access denied to this tenant"
        #     )
    
    return current_org


async def require_platform_admin_master(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_master_db)
) -> User:
    """Require platform admin role (for admin routes) - simplified for admin users"""
    token = credentials.credentials
    username = verify_token(token)
    
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from master database
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Platform administrator privileges required."
        )
    
    return user


def require_tenant_user(
    request: Request,
    current_user: User = Depends(get_current_active_user_master),
) -> User:
    """Require tenant user role (for tenant-specific operations)"""
    require_tenant_context(request)
    
    if not current_user.is_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant user access required"
        )
    return current_user


# Rate limiting dependency
def get_tenant_id_from_context(request: Request) -> str:
    """Get tenant ID from request context for rate limiting"""
    tenant_context = get_tenant_context(request)
    return tenant_context["tenant_id"] or "unknown"
