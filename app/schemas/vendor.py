from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from ..models.vendor import VendorCategory, PaymentTerms


class VendorBase(BaseModel):
    """Base vendor schema"""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    website: Optional[str] = Field(None, max_length=500)
    contact_person: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    tax_id: Optional[str] = Field(None, max_length=50)
    payment_terms: PaymentTerms = PaymentTerms.NET_30
    credit_limit: float = Field(default=0.0, ge=0)
    category: VendorCategory = VendorCategory.OTHER
    is_active: bool = True
    rating: int = Field(default=5, ge=1, le=5)
    bank_details: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class VendorCreate(VendorBase):
    """Schema for creating a vendor"""
    pass


class VendorUpdate(BaseModel):
    """Schema for updating a vendor"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    website: Optional[str] = Field(None, max_length=500)
    contact_person: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    tax_id: Optional[str] = Field(None, max_length=50)
    payment_terms: Optional[PaymentTerms] = None
    credit_limit: Optional[float] = Field(None, ge=0)
    category: Optional[VendorCategory] = None
    is_active: Optional[bool] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    bank_details: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class VendorResponse(VendorBase):
    """Schema for vendor response"""
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VendorListResponse(BaseModel):
    """Schema for vendor list response"""
    vendors: List[VendorResponse]
    total: int
    page: int
    size: int
    pages: int


class VendorStats(BaseModel):
    """Schema for vendor statistics"""
    total_vendors: int
    active_vendors: int
    inactive_vendors: int
    by_category: dict
    by_payment_terms: dict
    average_rating: float
