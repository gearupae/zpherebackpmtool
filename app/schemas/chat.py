from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class ChatRoomBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_private: bool = False


class ChatRoomCreate(ChatRoomBase):
    pass


class ChatRoom(ChatRoomBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class ChatMessage(BaseModel):
    id: str
    room_id: str
    user_id: str
    content: str
    edited: bool
    deleted: bool
    sent_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
