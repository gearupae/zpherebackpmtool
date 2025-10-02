from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime


class CustomerBase(BaseModel):
    """Base customer schema"""
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    job_title: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    customer_type: str = "prospect"
    source: Optional[str] = None
    credit_limit: Optional[int] = None
    payment_terms: str = "net_30"
    notes: Optional[str] = None
    tags: List[str] = []
    custom_fields: Dict[str, Any] = {}


class CustomerCreate(CustomerBase):
    """Schema for creating a customer"""
    pass


class CustomerUpdate(BaseModel):
    """Schema for updating a customer"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    job_title: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    customer_type: Optional[str] = None
    source: Optional[str] = None
    credit_limit: Optional[int] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class Customer(CustomerBase):
    """Customer schema for responses"""
    id: str
    organization_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    full_name: str
    display_name: str
    
    class Config:
        from_attributes = True


class CustomerList(BaseModel):
    """Schema for customer list responses"""
    customers: List[Customer]
    total: int
    page: int
    size: int
    pages: int


class CustomerStats(BaseModel):
    """Customer statistics"""
    total_customers: int
    active_customers: int
    prospects: int
    clients: int
    leads: int
    inactive_customers: int
    total_projects: int
    total_revenue: int  # In cents
