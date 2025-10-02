from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime
from ..models.user import UserRole, UserStatus


class UserBase(BaseModel):
    email: EmailStr
    username: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    bio: Optional[str] = None
    timezone: str = "UTC"
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    password: str
    organization_id: Optional[str] = None
    role: UserRole = UserRole.MEMBER
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class UserRegister(BaseModel):
    """Schema for user registration with organization creation"""
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    organization_name: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    timezone: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    notification_settings: Optional[Dict[str, Any]] = None


class UserInDB(UserBase):
    id: str
    organization_id: str
    role: UserRole
    status: UserStatus
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    preferences: Dict[str, Any] = {}
    notification_settings: Dict[str, Any] = {}
    
    class Config:
        from_attributes = True


class User(UserInDB):
    """Public user schema (excludes sensitive information)"""
    pass


class UserProfile(BaseModel):
    """Extended user profile with additional information"""
    id: str
    email: EmailStr
    username: str
    first_name: str
    last_name: str
    full_name: str
    phone: Optional[str] = None
    bio: Optional[str] = None
    timezone: str = "UTC"
    avatar_url: Optional[str] = None
    role: UserRole
    status: UserStatus
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    organization_name: str
    preferences: Dict[str, Any] = {}
    notification_settings: Dict[str, Any] = {}
    
    class Config:
        from_attributes = True


class UserInvite(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.MEMBER
    first_name: Optional[str] = None
    last_name: Optional[str] = None
