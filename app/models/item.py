from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Integer, JSON, Enum
from sqlalchemy.orm import relationship
from .base import UUIDBaseModel
import enum


class ItemType(str, enum.Enum):
    SERVICE = "service"
    PRODUCT = "product"
    EXPENSE = "expense"
    TIME = "time"
    MATERIAL = "material"


class TaxType(str, enum.Enum):
    NONE = "none"
    TAXABLE = "taxable"
    EXEMPT = "exempt"


class Item(UUIDBaseModel):
    """Item/Service model for proposals and invoices"""
    __tablename__ = "items"
    
    # Basic item info
    name = Column(String(255), nullable=False)
    description = Column(Text)
    sku = Column(String(100))  # Stock keeping unit / service code
    
    # Organization relationship (multi-tenancy)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Item classification
    item_type = Column(Enum(ItemType), default=ItemType.SERVICE)
    category = Column(String(100))  # Custom category for organization
    
    # Pricing information
    unit_price = Column(Integer, default=0)  # Default unit price in cents
    cost = Column(Integer, default=0)  # Cost price in cents (for margin calculation)
    unit = Column(String(50), default="each")  # unit, hour, piece, kg, etc.
    
    # Tax settings
    tax_type = Column(Enum(TaxType), default=TaxType.TAXABLE)
    default_tax_rate = Column(Integer, default=0)  # Default tax rate percentage * 100
    
    # Inventory (for products)
    track_inventory = Column(Boolean, default=False)
    current_stock = Column(Integer, default=0)
    minimum_stock = Column(Integer, default=0)
    
    # Settings and metadata
    is_active = Column(Boolean, default=True)
    is_billable = Column(Boolean, default=True)
    tags = Column(JSON, default=list)  # Tags for categorization
    custom_fields = Column(JSON, default=dict)  # Custom field definitions
    
    # Additional settings
    notes = Column(Text)  # Internal notes
    
    # Relationships
    organization = relationship("Organization", back_populates="items")
    
    @property
    def display_name(self):
        """Display name with SKU if available"""
        if self.sku:
            return f"{self.name} ({self.sku})"
        return self.name
    
    @property
    def unit_price_display(self):
        """Unit price in dollars"""
        return self.unit_price / 100.0
    
    @property
    def cost_display(self):
        """Cost in dollars"""
        return self.cost / 100.0
    
    @property
    def margin_percentage(self):
        """Calculate profit margin percentage"""
        if self.cost > 0:
            return ((self.unit_price - self.cost) / self.cost) * 100
        return 0.0
    
    def __repr__(self):
        return f"<Item(name='{self.name}', type='{self.item_type}', price='{self.unit_price}')>"
