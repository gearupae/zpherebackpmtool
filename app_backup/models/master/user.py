"""
Master database models - User (authentication and organization membership)
"""
from sqlalchemy import Column, String, Boolean, ForeignKey, Enum, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid
from ...db.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    CLIENT = "client"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"


class User(Base):
    """User model in master database - only authentication and organization data"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Basic user info
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    
    # Authentication
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    status = Column(Enum(UserStatus), default=UserStatus.PENDING)
    
    # Organization and role (master database only stores this)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.MEMBER)
    
    # Profile information
    avatar_url = Column(String(500))
    timezone = Column(String(50), default="UTC")
    phone = Column(String(20))
    bio = Column(String(500))
    
    # Preferences and settings
    preferences = Column(JSON, default=dict)
    notification_settings = Column(JSON, default=dict)
    
    # Authentication tracking
    last_login = Column(DateTime(timezone=True))
    password_changed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships (master database only)
    organization = relationship("Organization", back_populates="users")
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN
    
    @property
    def is_manager(self):
        return self.role in [UserRole.ADMIN, UserRole.MANAGER]
    
    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role}')>"
