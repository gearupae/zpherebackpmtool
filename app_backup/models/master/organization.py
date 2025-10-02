"""
Master database models - Organization (tenant management)
"""
from sqlalchemy import Column, String, Text, Boolean, JSON, Integer, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ...db.database import Base
import uuid


class Organization(Base):
    """Organization model in master database - tenant management"""
    __tablename__ = "organizations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    domain = Column(String(255))  # For domain-based tenant identification
    
    # Tenant database information
    database_name = Column(String(100))  # Name of the tenant database
    database_created = Column(Boolean, default=False)
    
    # Subscription and billing
    is_active = Column(Boolean, default=True)
    subscription_tier = Column(String(50), default="starter")  # starter, professional, business, enterprise
    max_users = Column(Integer, default=3)
    max_projects = Column(Integer, default=5)
    
    # Settings and customization
    settings = Column(JSON, default=dict)  # Organization-specific settings
    branding = Column(JSON, default=dict)  # Custom branding for white-label
    
    # Relationships (master database only)
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Organization(name='{self.name}', slug='{self.slug}')>"
