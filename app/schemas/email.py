from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class EmailConfigBase(BaseModel):
    provider: Optional[str] = Field(None, description="smtp|gmail|outlook")
    host: Optional[str] = None
    port: Optional[int] = Field(587, ge=1, le=65535)
    security: Optional[str] = Field("starttls", description="starttls|ssl|none")
    username: Optional[str] = None
    from_email: Optional[EmailStr] = None
    from_name: Optional[str] = None


class EmailConfigUpdate(EmailConfigBase):
    password: Optional[str] = Field(None, description="SMTP password or app password")
    is_active: Optional[bool] = True


class EmailConfig(EmailConfigBase):
    is_active: bool = True
    is_configured: bool = False

    class Config:
        from_attributes = True
