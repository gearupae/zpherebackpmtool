"""Focus management models (Focus Blocks)"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import UUIDBaseModel


class FocusBlock(UUIDBaseModel):
    """A scheduled focus window during which notifications should be silenced.
    Belongs to a user within an organization (tenant DB).
    """
    __tablename__ = "focus_blocks"

    # Owner and scope
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)

    # Window
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    timezone = Column(String(50), default="UTC")

    # Metadata
    reason = Column(Text)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization")
    created_by = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<FocusBlock(user='{self.user_id}', start='{self.start_time}', end='{self.end_time}', tz='{self.timezone}')>"
