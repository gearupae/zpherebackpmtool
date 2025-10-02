from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime

from ....api.deps_tenant import get_master_db as get_db
from ....models.user import User
from ....models.organization import Organization
from ....models.module import Module, TenantModule
from ....schemas.module import (
    ModuleInDB, ModuleCreate, ModuleUpdate, TenantModuleCreate, 
    TenantModuleUpdate, TenantModuleStats, ModuleWithTenantStatus
)
from ...deps_tenant import require_platform_admin_master as require_platform_admin

router = APIRouter()


@router.get("/", response_model=List[ModuleInDB])
async def get_all_modules(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
) -> Any:
    """Get all platform modules"""
    try:
        query = select(Module)
        
        if category:
            query = query.where(Module.category == category)
        if is_available is not None:
            query = query.where(Module.is_available == is_available)
            
        query = query.order_by(Module.category, Module.name)
        
        result = await db.execute(query)
        modules = result.scalars().all()
        
        return modules
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch modules: {str(e)}"
        )


@router.post("/", response_model=ModuleInDB)
async def create_module(
    module_data: ModuleCreate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new platform module"""
    try:
        # Check if module with same name exists
        existing_query = select(Module).where(Module.name == module_data.name)
        existing_result = await db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Module with this name already exists"
            )
        
        # Create new module
        module = Module(**module_data.dict())
        db.add(module)
        await db.commit()
        await db.refresh(module)
        
        return module
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create module: {str(e)}"
        )


@router.put("/{module_id}", response_model=ModuleInDB)
async def update_module(
    module_id: str,
    module_data: ModuleUpdate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update a platform module"""
    try:
        # Get existing module
        query = select(Module).where(Module.id == module_id)
        result = await db.execute(query)
        module = result.scalar_one_or_none()
        
        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found"
            )
        
        # Update module fields
        update_data = module_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(module, field, value)
        
        module.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(module)
        
        return module
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update module: {str(e)}"
        )


@router.get("/stats", response_model=List[TenantModuleStats])
async def get_module_statistics(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get module usage statistics across all tenants"""
    try:
        # Get all modules with their usage stats
        query = select(
            Module.id,
            Module.name,
            Module.category,
            Module.price_per_month,
            func.count(Organization.id).label('total_tenants'),
            func.count(
                func.case(
                    (and_(TenantModule.is_enabled == True), 1),
                    else_=None
                )
            ).label('enabled_tenants'),
            func.count(
                func.case(
                    (and_(TenantModule.is_enabled == False), 1),
                    else_=None
                )
            ).label('disabled_tenants')
        ).select_from(
            Module
        ).outerjoin(
            TenantModule, Module.id == TenantModule.module_id
        ).outerjoin(
            Organization, TenantModule.tenant_id == Organization.id
        ).group_by(
            Module.id, Module.name, Module.category, Module.price_per_month
        ).order_by(Module.category, Module.name)
        
        result = await db.execute(query)
        stats_data = result.all()
        
        # Calculate total tenants for percentage
        total_tenants_query = select(func.count(Organization.id)).where(Organization.is_active == True)
        total_tenants_result = await db.execute(total_tenants_query)
        total_tenant_count = total_tenants_result.scalar() or 0
        
        stats = []
        for row in stats_data:
            enabled_count = row.enabled_tenants or 0
            monthly_revenue = enabled_count * row.price_per_month
            usage_percentage = (enabled_count / total_tenant_count * 100) if total_tenant_count > 0 else 0
            
            stats.append(TenantModuleStats(
                module_id=row.id,
                module_name=row.name,
                category=row.category,
                price_per_month=row.price_per_month,
                total_tenants=total_tenant_count,
                enabled_tenants=enabled_count,
                disabled_tenants=(row.disabled_tenants or 0),
                monthly_revenue=monthly_revenue,
                usage_percentage=round(usage_percentage, 1)
            ))
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch module statistics: {str(e)}"
        )


@router.get("/tenant/{tenant_id}", response_model=List[ModuleWithTenantStatus])
async def get_tenant_modules(
    tenant_id: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get all modules with their status for a specific tenant"""
    try:
        # Verify tenant exists
        tenant_query = select(Organization).where(Organization.id == tenant_id)
        tenant_result = await db.execute(tenant_query)
        if not tenant_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Get all modules with tenant status
        query = select(
            Module,
            TenantModule.is_enabled,
            TenantModule.id.label('tenant_module_id')
        ).outerjoin(
            TenantModule, 
            and_(Module.id == TenantModule.module_id, TenantModule.tenant_id == tenant_id)
        ).order_by(Module.category, Module.name)
        
        result = await db.execute(query)
        module_data = result.all()
        
        modules = []
        for row in module_data:
            module_dict = {
                "id": row.Module.id,
                "name": row.Module.name,
                "description": row.Module.description,
                "category": row.Module.category,
                "price_per_month": row.Module.price_per_month,
                "is_core": row.Module.is_core,
                "is_available": row.Module.is_available,
                "features": row.Module.features,
                "created_at": row.Module.created_at,
                "updated_at": row.Module.updated_at,
                "is_enabled_for_tenant": row.is_enabled if row.is_enabled is not None else False,
                "tenant_module_id": row.tenant_module_id
            }
            modules.append(ModuleWithTenantStatus(**module_dict))
        
        return modules
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant modules: {str(e)}"
        )


@router.post("/tenant/{tenant_id}/enable/{module_id}")
async def enable_module_for_tenant(
    tenant_id: str,
    module_id: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Enable a module for a specific tenant"""
    try:
        # Verify tenant and module exist
        tenant_query = select(Organization).where(Organization.id == tenant_id)
        tenant_result = await db.execute(tenant_query)
        if not tenant_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        module_query = select(Module).where(Module.id == module_id)
        module_result = await db.execute(module_query)
        module = module_result.scalar_one_or_none()
        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found"
            )
        
        if not module.is_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Module is not available"
            )
        
        # Check if tenant-module relationship exists
        tenant_module_query = select(TenantModule).where(
            and_(TenantModule.tenant_id == tenant_id, TenantModule.module_id == module_id)
        )
        tenant_module_result = await db.execute(tenant_module_query)
        tenant_module = tenant_module_result.scalar_one_or_none()
        
        if tenant_module:
            # Update existing relationship
            tenant_module.is_enabled = True
            tenant_module.enabled_at = datetime.utcnow()
            tenant_module.disabled_at = None
            tenant_module.updated_at = datetime.utcnow()
        else:
            # Create new relationship
            tenant_module = TenantModule(
                tenant_id=tenant_id,
                module_id=module_id,
                is_enabled=True
            )
            db.add(tenant_module)
        
        await db.commit()
        
        return {
            "message": f"Module '{module.name}' enabled for tenant",
            "tenant_id": tenant_id,
            "module_id": module_id,
            "is_enabled": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable module: {str(e)}"
        )


@router.post("/tenant/{tenant_id}/disable/{module_id}")
async def disable_module_for_tenant(
    tenant_id: str,
    module_id: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Disable a module for a specific tenant"""
    try:
        # Verify tenant and module exist
        tenant_query = select(Organization).where(Organization.id == tenant_id)
        tenant_result = await db.execute(tenant_query)
        if not tenant_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        module_query = select(Module).where(Module.id == module_id)
        module_result = await db.execute(module_query)
        module = module_result.scalar_one_or_none()
        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found"
            )
        
        if module.is_core:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Core modules cannot be disabled"
            )
        
        # Find tenant-module relationship
        tenant_module_query = select(TenantModule).where(
            and_(TenantModule.tenant_id == tenant_id, TenantModule.module_id == module_id)
        )
        tenant_module_result = await db.execute(tenant_module_query)
        tenant_module = tenant_module_result.scalar_one_or_none()
        
        if tenant_module:
            # Update existing relationship
            tenant_module.is_enabled = False
            tenant_module.disabled_at = datetime.utcnow()
            tenant_module.updated_at = datetime.utcnow()
        else:
            # Create disabled relationship
            tenant_module = TenantModule(
                tenant_id=tenant_id,
                module_id=module_id,
                is_enabled=False,
                disabled_at=datetime.utcnow()
            )
            db.add(tenant_module)
        
        await db.commit()
        
        return {
            "message": f"Module '{module.name}' disabled for tenant",
            "tenant_id": tenant_id,
            "module_id": module_id,
            "is_enabled": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable module: {str(e)}"
        )


