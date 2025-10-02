"""
Pydantic schemas for delivery notes
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel
from ..models.delivery_note import DeliveryStatus


class DeliveryNoteItemBase(BaseModel):
    """Base schema for delivery note items"""
    item_name: str
    description: Optional[str] = None
    quantity_ordered: int
    quantity_delivered: int = 0
    unit_price: Optional[int] = None  # In cents
    

class DeliveryNoteItemCreate(DeliveryNoteItemBase):
    """Schema for creating delivery note items"""
    item_id: Optional[str] = None
    invoice_item_reference: Optional[Dict[str, Any]] = None


class DeliveryNoteItemUpdate(BaseModel):
    """Schema for updating delivery note items"""
    item_name: Optional[str] = None
    description: Optional[str] = None
    quantity_delivered: Optional[int] = None
    unit_price: Optional[int] = None


class DeliveryNoteItem(DeliveryNoteItemBase):
    """Schema for delivery note item responses"""
    id: str
    delivery_note_id: str
    item_id: Optional[str] = None
    invoice_item_reference: Optional[Dict[str, Any]] = None
    quantity_remaining: int
    is_fully_delivered: bool
    delivery_percentage: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DeliveryNoteBase(BaseModel):
    """Base schema for delivery notes"""
    delivery_date: datetime
    delivery_address: str
    delivery_contact_name: Optional[str] = None
    delivery_contact_phone: Optional[str] = None
    driver_name: Optional[str] = None
    vehicle_info: Optional[str] = None
    tracking_number: Optional[str] = None
    notes: Optional[str] = None


class DeliveryNoteCreate(DeliveryNoteBase):
    """Schema for creating delivery notes"""
    invoice_id: str
    items: List[DeliveryNoteItemCreate] = []


class DeliveryNoteUpdate(BaseModel):
    """Schema for updating delivery notes"""
    delivery_date: Optional[datetime] = None
    delivery_address: Optional[str] = None
    delivery_contact_name: Optional[str] = None
    delivery_contact_phone: Optional[str] = None
    driver_name: Optional[str] = None
    vehicle_info: Optional[str] = None
    tracking_number: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[DeliveryStatus] = None
    items: Optional[List[DeliveryNoteItemUpdate]] = None


class DeliveryNote(DeliveryNoteBase):
    """Schema for delivery note responses"""
    id: str
    delivery_note_number: str
    organization_id: str
    invoice_id: str
    created_by_id: str
    status: DeliveryStatus
    total_items: int
    delivered_items: int
    is_complete: bool
    completion_percentage: float
    items: List[DeliveryNoteItem] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DeliveryNoteList(BaseModel):
    """Schema for delivery note list responses"""
    delivery_notes: List[DeliveryNote]
    total: int
    page: int
    size: int
    pages: int


class DeliveryNoteStats(BaseModel):
    """Schema for delivery note statistics"""
    total_delivery_notes: int
    draft_notes: int
    in_transit_notes: int
    delivered_notes: int
    cancelled_notes: int
    average_delivery_time: Optional[float] = None
    completion_rate: float


class InvoiceDeliveryStatus(BaseModel):
    """Schema for invoice delivery status summary"""
    invoice_id: str
    invoice_number: str
    total_items: int
    items_with_deliveries: int
    total_ordered_quantity: int
    total_delivered_quantity: int
    remaining_quantity: int
    delivery_percentage: float
    is_fully_delivered: bool
    delivery_notes_count: int
    latest_delivery_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True
