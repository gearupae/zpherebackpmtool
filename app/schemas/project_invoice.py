from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator
from datetime import datetime
from ..models.project_invoice import InvoiceStatus, InvoiceType


class InvoiceItemBase(BaseModel):
    """Base invoice item schema"""
    description: str
    quantity: int = 1
    unit_price: int = 0  # In cents
    item_type: str = "service"
    task_id: Optional[str] = None
    tax_rate: int = 0  # Tax rate percentage * 100
    discount_rate: int = 0  # Discount rate percentage * 100


class InvoiceItemCreate(InvoiceItemBase):
    """Schema for creating an invoice item"""
    pass


class InvoiceItemUpdate(BaseModel):
    """Schema for updating an invoice item"""
    description: Optional[str] = None
    quantity: Optional[int] = None
    unit_price: Optional[int] = None
    item_type: Optional[str] = None
    task_id: Optional[str] = None
    tax_rate: Optional[int] = None
    discount_rate: Optional[int] = None


class InvoiceItem(InvoiceItemBase):
    """Invoice item schema for responses"""
    id: str
    invoice_id: str
    amount: int  # In cents
    tax_amount: int  # In cents
    discount_amount: int  # In cents
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class InlineInvoiceItem(BaseModel):
    """Lightweight invoice item as stored in ProjectInvoice.items JSON"""
    description: str
    quantity: int
    unit_price: int  # In cents
    item_type: Optional[str] = "service"
    tax_rate: int  # percentage * 100 (e.g., 500 => 5.00%)
    discount_rate: int  # percentage * 100 (e.g., 250 => 2.50%)
    amount: int  # base amount (quantity * unit_price) in cents
    tax_amount: int  # in cents
    discount_amount: int  # in cents


class ProjectInvoiceBase(BaseModel):
    """Base project invoice schema"""
    title: str
    description: Optional[str] = None
    invoice_type: InvoiceType = InvoiceType.PROJECT
    currency: str = "usd"
    exchange_rate: int = 100
    payment_terms: str = "net_30"
    invoice_date: datetime
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    is_recurring: bool = False
    recurring_interval: Optional[str] = None
    next_invoice_date: Optional[datetime] = None
    tags: List[str] = []
    custom_fields: Dict[str, Any] = {}


class ProjectInvoiceCreate(ProjectInvoiceBase):
    """Schema for creating a project invoice"""
    project_id: str
    customer_id: str
    items: List[InvoiceItemCreate] = []


class ProjectInvoiceUpdate(BaseModel):
    """Schema for updating a project invoice"""
    title: Optional[str] = None
    description: Optional[str] = None
    invoice_type: Optional[InvoiceType] = None
    currency: Optional[str] = None
    exchange_rate: Optional[int] = None
    payment_terms: Optional[str] = None
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    status: Optional[InvoiceStatus] = None
    notes: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    is_recurring: Optional[bool] = None
    recurring_interval: Optional[str] = None
    next_invoice_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class ProjectInvoice(ProjectInvoiceBase):
    """Project invoice schema for responses"""
    id: str
    invoice_number: str
    organization_id: str
    project_id: str
    customer_id: str
    created_by_id: str
    status: InvoiceStatus
    subtotal: int  # In cents
    tax_amount: int  # In cents
    discount_amount: int  # In cents
    total_amount: int  # In cents
    amount_paid: int  # In cents
    balance_due: int  # In cents
    sent_date: Optional[datetime] = None
    viewed_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    items: List[InlineInvoiceItem] = []
    payment_history: List[Dict[str, Any]] = []
    late_fees: int  # In cents
    reminder_sent_count: int
    last_reminder_sent: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    is_overdue: bool
    days_overdue: int
    payment_percentage: float
    status_color: str
    
    class Config:
        from_attributes = True


class ProjectInvoiceList(BaseModel):
    """Schema for project invoice list responses"""
    invoices: List[ProjectInvoice]
    total: int
    page: int
    size: int
    pages: int


class InvoiceStats(BaseModel):
    """Invoice statistics"""
    total_invoices: int
    draft_invoices: int
    sent_invoices: int
    pending_invoices: int
    paid_invoices: int
    overdue_invoices: int
    total_amount: int  # In cents
    total_paid: int  # In cents
    total_outstanding: int  # In cents
    overdue_amount: int  # In cents
    average_payment_time: int  # In days
