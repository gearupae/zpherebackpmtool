"""
Dependencies for admin-only endpoints
"""
from typing import Generator
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db.database import get_db
from ..models.user import User, UserRole
from ..models.organization import Organization
from .deps import get_current_active_user


async def get_platform_admin(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to ensure the current user is a platform administrator.
    Platform admins are users with ADMIN role in the special admin organization.
    """
    # Check if user has ADMIN role
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Platform administrator role required."
        )
    
    # Check if user belongs to the platform admin organization
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Check if this is the platform admin organization
    settings = organization.settings or {}
    if not settings.get("is_platform_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Platform administrator privileges required."
        )
    
    return current_user


async def require_platform_admin(
    current_user: User = Depends(get_platform_admin),
) -> User:
    """
    Simple dependency alias for requiring platform admin access
    """
    return current_user
