from sqlalchemy import Column, String, Integer, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from .base import UUIDBaseModel


class CustomerAttachment(UUIDBaseModel):
    """Attachment linked to a customer"""
    __tablename__ = "customer_attachments"

    customer_id = Column(String, ForeignKey("customers.id"), nullable=False, index=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)

    original_filename = Column(String(500))
    content_type = Column(String(100))
    size = Column(Integer)  # bytes
    storage_path = Column(String(1000))

    uploaded_by = Column(String, ForeignKey("users.id"))
    description = Column(Text)
    tags = Column(JSON, default=list)

    # Relationships
    customer = relationship("Customer", back_populates="attachments")

