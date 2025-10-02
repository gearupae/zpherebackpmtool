from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, validator, Field
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


class CustomerAttachment(BaseModel):
    id: str
    customer_id: str
    original_filename: Optional[str] = None
    content_type: Optional[str] = None
    size: Optional[int] = None
    storage_path: Optional[str] = None
    uploaded_by: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CustomerAttachmentUpdate(BaseModel):
    description: Optional[str] = None
    tags: Optional[List[str]] = None

class Customer(CustomerBase):
    """Customer schema for responses"""
    id: str
    organization_id: Optional[str] = None  # Optional for tenant context
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    full_name: str
    display_name: str
    
    # Related
    attachments: List[CustomerAttachment] = []
    
    @validator('customer_type', pre=True, always=True)
    def validate_customer_type(cls, v):
        return v if v is not None else "prospect"
    
    @validator('payment_terms', pre=True, always=True)
    def validate_payment_terms(cls, v):
        return v if v is not None else "net_30"
    
    @validator('tags', pre=True, always=True)
    def validate_tags(cls, v):
        return v if v is not None else []
    
    @validator('custom_fields', pre=True, always=True)
    def validate_custom_fields(cls, v):
        return v if v is not None else {}
    
    @validator('is_active', pre=True, always=True)
    def validate_is_active(cls, v):
        return v if v is not None else True
    
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
