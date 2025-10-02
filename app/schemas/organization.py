from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime


class OrganizationBase(BaseModel):
    name: str
    description: Optional[str] = None
    domain: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    slug: str


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    branding: Optional[Dict[str, Any]] = None


class Organization(OrganizationBase):
    id: str
    slug: str
    is_active: bool
    subscription_tier: str
    max_users: int
    max_projects: int
    settings: Dict[str, Any] = {}
    branding: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
