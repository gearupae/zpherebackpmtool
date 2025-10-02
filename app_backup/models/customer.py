from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime, JSON, Integer
from sqlalchemy.orm import relationship
from .base import UUIDBaseModel


class Customer(UUIDBaseModel):
    """Customer/Client model for external contact management"""
    __tablename__ = "customers"
    
    # Basic contact info
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(20))
    
    # Company information
    company_name = Column(String(255))
    company_website = Column(String(500))
    job_title = Column(String(100))
    
    # Address information
    address_line_1 = Column(String(255))
    address_line_2 = Column(String(255))
    city = Column(String(100))
    state = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(100))
    
    # Organization relationship (multi-tenancy)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Customer status and classification
    is_active = Column(Boolean, default=True)
    customer_type = Column(String(50), default="prospect")  # prospect, client, lead, inactive
    source = Column(String(100))  # How they found us (referral, website, etc.)
    
    # Financial information
    credit_limit = Column(Integer)  # In cents
    payment_terms = Column(String(50), default="net_30")  # net_15, net_30, net_60
    
    # Notes and custom fields
    notes = Column(Text)
    tags = Column(JSON, default=list)  # List of tags for categorization
    custom_fields = Column(JSON, default=dict)  # Custom field definitions
    
    # Relationships
    organization = relationship("Organization", back_populates="customers")
    projects = relationship("Project", back_populates="customer", cascade="all, delete-orphan")
    # proposals = relationship("Proposal", back_populates="customer", cascade="all, delete-orphan")  # Temporarily disabled
    invoices = relationship("ProjectInvoice", back_populates="customer", cascade="all, delete-orphan")
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def display_name(self):
        if self.company_name:
            return f"{self.full_name} - {self.company_name}"
        return self.full_name
    
    def __repr__(self):
        return f"<Customer(name='{self.full_name}', company='{self.company_name}')>"
