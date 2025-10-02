from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db.database import AsyncSessionLocal
from ..core.security import verify_token
from ..models.user import User
from ..models.organization import Organization

security = HTTPBearer()


async def get_db() -> Generator[AsyncSession, None, None]:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    token = credentials.credentials
    username = verify_token(token)
    
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
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


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_current_organization(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Organization:
    """Get current user's organization"""
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


def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Require admin role"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def require_manager(current_user: User = Depends(get_current_active_user)) -> User:
    """Require manager role or above"""
    if not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def require_customer_create_permission(current_user: User = Depends(get_current_active_user)) -> User:
    """Require permission to create customers"""
    from ..models.user import Permission
    if not current_user.has_permission(Permission.CREATE_CUSTOMER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create customers"
        )
    return current_user


# Tenant-specific permission functions that work with master user authentication
def require_tenant_customer_create_permission():
    """Require permission to create customers in tenant context"""
    def check_permission(current_user: User = Depends(get_current_active_user)) -> User:
        from ..models.user import Permission
        if not current_user.has_permission(Permission.CREATE_CUSTOMER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create customers"
            )
        return current_user
    return check_permission


def require_customer_edit_permission(current_user: User = Depends(get_current_active_user)) -> User:
    """Require permission to edit customers"""
    from ..models.user import Permission
    if not current_user.has_permission(Permission.EDIT_CUSTOMER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to edit customers"
        )
    return current_user


def require_customer_delete_permission(current_user: User = Depends(get_current_active_user)) -> User:
    """Require permission to delete customers"""
    from ..models.user import Permission
    if not current_user.has_permission(Permission.DELETE_CUSTOMER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete customers"
        )
    return current_user


# Rate limiting dependency
def get_tenant_id(request: Request, current_user: User = Depends(get_current_active_user)) -> str:
    """Get tenant ID for rate limiting"""
    return current_user.organization_id


# Optional user dependency (for public endpoints)
async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise"""
    try:
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ")[1]
        username = verify_token(token)
        
        if username is None:
            return None
        
        result = await db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if user and user.is_active:
            return user
        
        return None
    except Exception:
        return None
