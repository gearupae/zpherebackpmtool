from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from ..models.purchase_order import PurchaseOrderStatus, Priority, ItemUnit


class PurchaseOrderItemBase(BaseModel):
    """Base purchase order item schema"""
    # Either item_id (reference to catalog item) or item_name (ad-hoc) should be provided when creating
    item_id: Optional[str] = None
    item_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    quantity: int = Field(..., gt=0)
    unit: ItemUnit = ItemUnit.PIECES
    unit_price: float = Field(..., gt=0)
    notes: Optional[str] = None


class PurchaseOrderItemCreate(PurchaseOrderItemBase):
    """Schema for creating a purchase order item"""
    pass


class PurchaseOrderItemUpdate(BaseModel):
    """Schema for updating a purchase order item"""
    item_id: Optional[str] = None
    item_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    quantity: Optional[int] = Field(None, gt=0)
    unit: Optional[ItemUnit] = None
    unit_price: Optional[float] = Field(None, gt=0)
    quantity_received: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class PurchaseOrderItemResponse(PurchaseOrderItemBase):
    """Schema for purchase order item response"""
    id: str
    purchase_order_id: str
    total_price: float
    quantity_received: int
    quantity_pending: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PurchaseOrderBase(BaseModel):
    """Base purchase order schema"""
    vendor_id: str
    order_date: date
    expected_delivery_date: Optional[date] = None
    received_date: Optional[date] = None
    project_id: Optional[str] = None
    customer_id: Optional[str] = None
    priority: Priority = Priority.MEDIUM
    department: Optional[str] = Field(None, max_length=100)
    requested_by: str = Field(..., max_length=255)
    shipping_address: Optional[str] = None
    payment_method: str = Field(default="net_30", max_length=50)
    notes: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    internal_reference: Optional[str] = Field(None, max_length=100)


class PurchaseOrderCreate(PurchaseOrderBase):
    """Schema for creating a purchase order"""
    items: List[PurchaseOrderItemCreate] = Field(..., min_items=1)


class PurchaseOrderUpdate(BaseModel):
    """Schema for updating a purchase order"""
    vendor_id: Optional[str] = None
    order_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None
    received_date: Optional[date] = None
    status: Optional[PurchaseOrderStatus] = None
    priority: Optional[Priority] = None
    project_id: Optional[str] = None
    customer_id: Optional[str] = None
    department: Optional[str] = Field(None, max_length=100)
    requested_by: Optional[str] = Field(None, max_length=255)
    approved_by: Optional[str] = Field(None, max_length=255)
    shipping_address: Optional[str] = None
    payment_method: Optional[str] = Field(None, max_length=50)
    subtotal: Optional[float] = Field(None, ge=0)
    tax_amount: Optional[float] = Field(None, ge=0)
    shipping_cost: Optional[float] = Field(None, ge=0)
    total_amount: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    internal_reference: Optional[str] = Field(None, max_length=100)
    # Optional full replacement of items
    items: Optional[List[PurchaseOrderItemCreate]] = None


class PurchaseOrderResponse(PurchaseOrderBase):
    """Schema for purchase order response"""
    id: str
    po_number: str
    organization_id: str
    status: PurchaseOrderStatus
    received_date: Optional[date]
    approved_by: Optional[str]
    subtotal: float
    tax_amount: float
    shipping_cost: float
    total_amount: float
    created_at: datetime
    updated_at: datetime
    
    # Related data
    vendor_name: Optional[str] = None
    items: List[PurchaseOrderItemResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PurchaseOrderListResponse(BaseModel):
    """Schema for purchase order list response"""
    purchase_orders: List[PurchaseOrderResponse]
    total: int
    page: int
    size: int
    pages: int


class PurchaseOrderStats(BaseModel):
    """Schema for purchase order statistics"""
    total_orders: int
    pending_orders: int
    approved_orders: int
    received_orders: int
    cancelled_orders: int
    total_spent: float
    average_order_value: float
    by_status: dict
    by_priority: dict
    by_department: dict
    monthly_trends: dict


class PurchaseOrderStatusUpdate(BaseModel):
    """Schema for updating purchase order status"""
    status: PurchaseOrderStatus
    approved_by: Optional[str] = None
    received_date: Optional[date] = None
    notes: Optional[str] = None
