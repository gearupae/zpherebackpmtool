"""
Database dependencies for multi-tenant architecture
"""
from typing import Generator
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .tenant_manager import tenant_manager
from ..models.user import User
from ..models.organization import Organization


async def get_master_db_session() -> AsyncSession:
    """Get master database session for organizations and users"""
    session = await tenant_manager.get_master_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_tenant_db_session(
    current_user: User = Depends(lambda: None),  # Will be properly injected
    current_org: Organization = Depends(lambda: None)  # Will be properly injected
) -> AsyncSession:
    """Get tenant database session based on current organization"""
    if not current_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context required for tenant database access"
        )
    
    session = await tenant_manager.get_tenant_session(current_org.id)
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def create_tenant_db_dependency(organization_id: str):
    """Create a tenant database dependency for a specific organization"""
    async def get_specific_tenant_db() -> AsyncSession:
        session = await tenant_manager.get_tenant_session(organization_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    return get_specific_tenant_db
