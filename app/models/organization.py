from sqlalchemy import Column, String, Text, Boolean, JSON, Integer
from sqlalchemy.orm import relationship
from .base import UUIDBaseModel


class Organization(UUIDBaseModel):
    """Organization/Tenant model for multi-tenancy"""
    __tablename__ = "organizations"
    
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    domain = Column(String(255))  # For domain-based tenant identification
    
    # Subscription and billing
    is_active = Column(Boolean, default=True)
    subscription_tier = Column(String(50), default="starter")  # starter, professional, business, enterprise
    max_users = Column(Integer, default=3)
    max_projects = Column(Integer, default=5)
    
    # Settings and customization
    settings = Column(JSON, default=dict)  # Organization-specific settings
    branding = Column(JSON, default=dict)  # Custom branding for white-label
    
    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")
    workspaces = relationship("Workspace", back_populates="organization", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="organization", uselist=False)
    customers = relationship("app.models.customer.Customer", back_populates="organization", cascade="all, delete-orphan")
    items = relationship("Item", back_populates="organization", cascade="all, delete-orphan")
    # proposals = relationship("Proposal", back_populates="organization", cascade="all, delete-orphan")  # Temporarily disabled
    # proposal_templates = relationship("ProposalTemplate", back_populates="organization", cascade="all, delete-orphan")  # Temporarily disabled
    project_invoices = relationship("ProjectInvoice", back_populates="organization", cascade="all, delete-orphan")
    delivery_notes = relationship("DeliveryNote", back_populates="organization", cascade="all, delete-orphan")
    vendors = relationship("Vendor", back_populates="organization", cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="organization", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Organization(name='{self.name}', slug='{self.slug}')>"
