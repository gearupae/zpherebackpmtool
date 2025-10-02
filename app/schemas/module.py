from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class ModuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    price_per_month: float = 0.0
    is_core: bool = False
    is_available: bool = True
    features: Optional[str] = None


class ModuleCreate(ModuleBase):
    pass


class ModuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price_per_month: Optional[float] = None
    is_core: Optional[bool] = None
    is_available: Optional[bool] = None
    features: Optional[str] = None


class ModuleInDB(ModuleBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TenantModuleBase(BaseModel):
    tenant_id: str
    module_id: str
    is_enabled: bool = True


class TenantModuleCreate(TenantModuleBase):
    pass


class TenantModuleUpdate(BaseModel):
    is_enabled: Optional[bool] = None


class TenantModuleInDB(TenantModuleBase):
    id: str
    enabled_at: datetime
    disabled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ModuleWithTenantStatus(ModuleInDB):
    """Module with tenant-specific enablement status"""
    is_enabled_for_tenant: bool = False
    tenant_module_id: Optional[str] = None


class TenantModuleStats(BaseModel):
    """Statistics for module usage across tenants"""
    module_id: str
    module_name: str
    category: str
    price_per_month: float
    total_tenants: int
    enabled_tenants: int
    disabled_tenants: int
    monthly_revenue: float
    usage_percentage: float


