"""
Delivery Note models for tracking partial deliveries against invoices
"""
import enum
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from .base import UUIDBaseModel


class DeliveryStatus(str, enum.Enum):
    """Delivery note status"""
    DRAFT = "draft"
    PREPARED = "prepared"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class DeliveryNote(UUIDBaseModel):
    """Delivery note model for tracking shipments against invoices"""
    __tablename__ = "delivery_notes"
    
    # Basic delivery note info
    delivery_note_number = Column(String(100), unique=True, nullable=False, index=True)
    
    # Relationships
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    invoice_id = Column(String, ForeignKey("project_invoices.id"), nullable=False)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Delivery details
    delivery_date = Column(DateTime(timezone=True), nullable=False)
    delivery_address = Column(Text, nullable=False)
    delivery_contact_name = Column(String(255))
    delivery_contact_phone = Column(String(50))
    
    # Logistics
    driver_name = Column(String(255))
    vehicle_info = Column(String(255))
    tracking_number = Column(String(100))
    
    # Status and notes
    status = Column(SQLEnum(DeliveryStatus), default=DeliveryStatus.DRAFT)
    notes = Column(Text)
    
    # Metadata
    total_items = Column(Integer, default=0)
    delivered_items = Column(Integer, default=0)
    
    # Relationships
    organization = relationship("Organization", back_populates="delivery_notes")
    invoice = relationship("ProjectInvoice", back_populates="delivery_notes")
    created_by = relationship("User", foreign_keys=[created_by_id])
    items = relationship("DeliveryNoteItem", back_populates="delivery_note", cascade="all, delete-orphan")
    
    def calculate_totals(self):
        """Calculate total and delivered item counts"""
        self.total_items = len(self.items)
        self.delivered_items = sum(1 for item in self.items if item.quantity_delivered > 0)
    
    @property
    def is_complete(self):
        """Check if all items have been fully delivered"""
        return all(item.is_fully_delivered for item in self.items)
    
    @property
    def completion_percentage(self):
        """Calculate delivery completion percentage"""
        if not self.items:
            return 0
        
        total_ordered = sum(item.quantity_ordered for item in self.items)
        total_delivered = sum(item.quantity_delivered for item in self.items)
        
        if total_ordered == 0:
            return 0
        
        return (total_delivered / total_ordered) * 100
    
    def __repr__(self):
        try:
            return f"<DeliveryNote(number='{self.delivery_note_number}', status='{self.status}')>"
        except Exception:
            return f"<DeliveryNote(id='{getattr(self, 'id', 'unknown')}')>"


class DeliveryNoteItem(UUIDBaseModel):
    """Individual items in a delivery note with partial delivery tracking"""
    __tablename__ = "delivery_note_items"
    
    # Relationships
    delivery_note_id = Column(String, ForeignKey("delivery_notes.id"), nullable=False)
    item_id = Column(String, ForeignKey("items.id"), nullable=True)  # Optional reference to master item
    invoice_item_reference = Column(JSON)  # Store invoice item details for reference
    
    # Item details
    item_name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Quantities
    quantity_ordered = Column(Integer, nullable=False)  # Original invoice quantity
    quantity_delivered = Column(Integer, default=0)    # Delivered in this note
    quantity_remaining = Column(Integer, nullable=False)  # Calculated remaining quantity
    
    # Pricing (for reference)
    unit_price = Column(Integer)  # In cents
    
    # Relationships
    delivery_note = relationship("DeliveryNote", back_populates="items")
    item = relationship("Item", foreign_keys=[item_id])
    
    @property
    def is_fully_delivered(self):
        """Check if this item has been fully delivered"""
        return self.quantity_delivered >= self.quantity_ordered
    
    @property
    def delivery_percentage(self):
        """Calculate delivery percentage for this item"""
        if self.quantity_ordered == 0:
            return 0
        return (self.quantity_delivered / self.quantity_ordered) * 100
    
    def update_remaining_quantity(self):
        """Update the remaining quantity based on delivered quantity"""
        self.quantity_remaining = max(0, self.quantity_ordered - self.quantity_delivered)
    
    def __repr__(self):
        try:
            return f"<DeliveryNoteItem(item='{self.item_name}', delivered={self.quantity_delivered}/{self.quantity_ordered})>"
        except Exception:
            return f"<DeliveryNoteItem(id='{getattr(self, 'id', 'unknown')}')>"
