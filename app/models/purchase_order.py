from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Integer, Float, Date, Enum
from sqlalchemy.orm import relationship
from .base import UUIDBaseModel
import enum


class PurchaseOrderStatus(str, enum.Enum):
    """Purchase order status enumeration"""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    ORDERED = "ordered"
    RECEIVED = "received"
    CANCELLED = "cancelled"
    PARTIALLY_RECEIVED = "partially_received"


class Priority(str, enum.Enum):
    """Priority level enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class PurchaseOrder(UUIDBaseModel):
    """Purchase Order model"""
    __tablename__ = "purchase_orders"
    
    # Basic order information
    po_number = Column(String(50), nullable=False, unique=True, index=True)
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=False)
    
    # Optional associations
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True)
    
    # Dates
    order_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date)
    received_date = Column(Date)
    
    # Status and priority
    status = Column(Enum(PurchaseOrderStatus), default=PurchaseOrderStatus.DRAFT)
    priority = Column(Enum(Priority), default=Priority.MEDIUM)
    
    # Financial information
    subtotal = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    shipping_cost = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    
    # Request information
    department = Column(String(100))
    requested_by = Column(String(255))
    approved_by = Column(String(255))
    
    # Shipping and payment
    shipping_address = Column(Text)
    payment_method = Column(String(50), default="net_30")
    
    # Additional details
    notes = Column(Text)
    terms_and_conditions = Column(Text)
    internal_reference = Column(String(100))  # Internal tracking reference
    
    # Organization relationship (multi-tenancy)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Relationships
    organization = relationship("Organization", back_populates="purchase_orders")
    vendor = relationship("Vendor", back_populates="purchase_orders")
    project = relationship("Project")
    customer = relationship("Customer")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PurchaseOrder(po_number='{self.po_number}', status='{self.status}')>"


class ItemUnit(str, enum.Enum):
    """Item unit enumeration"""
    PIECES = "pcs"
    KILOGRAMS = "kg"
    POUNDS = "lbs"
    HOURS = "hrs"
    DAYS = "days"
    METERS = "m"
    LITERS = "l"
    BOXES = "box"
    SETS = "set"
    EACH = "each"


class PurchaseOrderItem(UUIDBaseModel):
    """Purchase Order Item model"""
    __tablename__ = "purchase_order_items"
    
    # Purchase order relationship
    purchase_order_id = Column(String, ForeignKey("purchase_orders.id"), nullable=False)
    
    # Optional reference to catalog item
    item_id = Column(String, ForeignKey("items.id"), nullable=True)
    
    # Item information (snapshotted at time of order)
    item_name = Column(String(255), nullable=False)
    description = Column(Text)
    sku = Column(String(100))  # Stock Keeping Unit
    category = Column(String(100))
    
    # Quantity and pricing
    quantity = Column(Integer, nullable=False)
    unit = Column(Enum(ItemUnit), default=ItemUnit.PIECES)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)  # quantity * unit_price
    
    # Receiving information
    quantity_received = Column(Integer, default=0)
    quantity_pending = Column(Integer, default=0)
    
    # Additional details
    notes = Column(Text)
    
    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="items")
    item = relationship("Item", lazy="joined")
    
    def __repr__(self):
        return f"<PurchaseOrderItem(item_name='{self.item_name}', quantity={self.quantity})>"
