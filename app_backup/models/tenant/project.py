"""
Tenant database models - Project (without organization_id)
"""
from sqlalchemy import Column, String, Text, Boolean, JSON, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
import enum
from ...db.tenant_manager import TenantBase
from ..base import UUIDBaseModel


class ProjectStatus(str, enum.Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProjectPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Project(UUIDBaseModel, TenantBase):
    """Project model in tenant database"""
    __tablename__ = "projects"
    
    # Basic project info
    name = Column(String(255), nullable=False)
    description = Column(Text)
    slug = Column(String(100), nullable=False, index=True)
    
    # Project details
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PLANNING)
    priority = Column(Enum(ProjectPriority), default=ProjectPriority.MEDIUM)
    
    # Dates
    start_date = Column(DateTime(timezone=True))
    due_date = Column(DateTime(timezone=True))
    completed_date = Column(DateTime(timezone=True))
    
    # Project management (references to master database via ID strings)
    owner_id = Column(String, nullable=False)  # User ID from master database
    customer_id = Column(String, ForeignKey("customers.id"))  # Local customer in tenant DB
    
    # Budget and billing
    budget = Column(Integer)  # Budget in cents
    hourly_rate = Column(Integer)  # Hourly rate in cents
    estimated_hours = Column(Integer)
    actual_hours = Column(Integer, default=0)
    
    # Settings and customization
    settings = Column(JSON, default=dict)
    custom_fields = Column(JSON, default=dict)
    
    # Flags
    is_template = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    is_public = Column(Boolean, default=False)
    
    # Relationships (within tenant database only)
    customer = relationship("Customer", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    invoices = relationship("ProjectInvoice", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project(name='{self.name}', status='{self.status}')>"


class ProjectMember(UUIDBaseModel, TenantBase):
    """Project member model in tenant database"""
    __tablename__ = "project_members"
    
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    user_id = Column(String, nullable=False)  # User ID from master database
    role = Column(String(50), default="member")  # admin, member, viewer
    
    # Permissions
    can_edit = Column(Boolean, default=True)
    can_delete = Column(Boolean, default=False)
    can_manage_members = Column(Boolean, default=False)
    
    # Relationships
    project = relationship("Project", back_populates="members")
    
    def __repr__(self):
        return f"<ProjectMember(project_id='{self.project_id}', user_id='{self.user_id}')>"
