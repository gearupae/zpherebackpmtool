"""Pydantic schemas for Focus Blocks"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class FocusBlockBase(BaseModel):
    start_time: datetime
    end_time: datetime
    timezone: str = Field(default="UTC", max_length=50)
    reason: Optional[str] = Field(default=None, max_length=2000)


class FocusBlockCreate(FocusBlockBase):
    pass


class FocusBlockUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    timezone: Optional[str] = Field(default=None, max_length=50)
    reason: Optional[str] = Field(default=None, max_length=2000)


class FocusBlock(FocusBlockBase):
    id: str
    user_id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
