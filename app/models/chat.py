from __future__ import annotations
from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime, Index, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from .base import UUIDBaseModel


class ChatRoomType(str, enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    DM = "dm"


class ChatRoom(UUIDBaseModel):
    __tablename__ = "chat_rooms"

    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, index=True)  # e.g., "general" or dm-<userA>-<userB>
    description = Column(Text)
    is_private = Column(Boolean, default=False)
    room_type = Column(SQLEnum(ChatRoomType), default=ChatRoomType.PUBLIC, nullable=False)

    # Relationships
    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan")
    members = relationship("ChatRoomMember", back_populates="room", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_chat_rooms_org_slug", "organization_id", "slug", unique=True),
    )


class ChatMessage(UUIDBaseModel):
    __tablename__ = "chat_messages"

    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    content = Column(Text, nullable=False)
    edited = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    room = relationship("ChatRoom", back_populates="messages")


class ChatRoomMember(UUIDBaseModel):
    __tablename__ = "chat_room_members"

    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    room = relationship("ChatRoom", back_populates="members")
