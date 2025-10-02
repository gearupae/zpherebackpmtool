from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Integer, Float, JSON, Enum
from sqlalchemy.orm import relationship
from .base import UUIDBaseModel
import enum


class VendorCategory(str, enum.Enum):
    """Vendor category enumeration"""
    OFFICE_SUPPLIES = "office_supplies"
    TECHNOLOGY = "technology"
    SERVICES = "services"
    MANUFACTURING = "manufacturing"
    CONSULTING = "consulting"
    MARKETING = "marketing"
    LEGAL = "legal"
    FINANCIAL = "financial"
    OTHER = "other"


class PaymentTerms(str, enum.Enum):
    """Payment terms enumeration"""
    NET_15 = "net_15"
    NET_30 = "net_30"
    NET_60 = "net_60"
    NET_90 = "net_90"
    COD = "cod"  # Cash on Delivery
    PREPAID = "prepaid"
    DUE_ON_RECEIPT = "due_on_receipt"


class Vendor(UUIDBaseModel):
    """Vendor/Supplier model for purchase management"""
    __tablename__ = "vendors"
    
    # Basic company information
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    phone = Column(String(20))
    website = Column(String(500))
    contact_person = Column(String(255))
    
    # Address information
    address = Column(String(255))
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))
    postal_code = Column(String(20))
    
    # Business information
    tax_id = Column(String(50))
    payment_terms = Column(Enum(PaymentTerms), default=PaymentTerms.NET_30)
    credit_limit = Column(Float, default=0.0)
    category = Column(Enum(VendorCategory), default=VendorCategory.OTHER)
    
    # Status and rating
    is_active = Column(Boolean, default=True)
    rating = Column(Integer, default=5)  # 1-5 star rating
    
    # Additional details
    bank_details = Column(Text)  # Bank account information
    notes = Column(Text)
    tags = Column(JSON, default=list)  # List of tags for categorization
    
    # Organization relationship (multi-tenancy)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Relationships
    organization = relationship("Organization", back_populates="vendors")
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Vendor(name='{self.name}', category='{self.category}')>"
