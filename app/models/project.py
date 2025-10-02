from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Enum, DateTime, JSON, Integer
from sqlalchemy.orm import relationship
import enum
from .base import UUIDBaseModel


class ProjectStatus(str, enum.Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class ProjectPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Project(UUIDBaseModel):
    """Project model"""
    __tablename__ = "projects"
    
    # Basic project info
    name = Column(String(255), nullable=False)
    description = Column(Text)
    slug = Column(String(100), nullable=False, index=True)
    
    # Organization and workspace relationships
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    workspace_id = Column(String, ForeignKey("workspaces.id"))
    
    # Project details
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PLANNING)
    priority = Column(Enum(ProjectPriority), default=ProjectPriority.MEDIUM)
    
    # Dates
    start_date = Column(DateTime(timezone=True))
    due_date = Column(DateTime(timezone=True))
    completed_date = Column(DateTime(timezone=True))
    
    # Project management
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"))  # External customer/client
    
    # Budget and billing
    budget = Column(Integer)  # Budget in cents
    hourly_rate = Column(Integer)  # Hourly rate in cents
    estimated_hours = Column(Integer)
    actual_hours = Column(Integer, default=0)
    
    # Settings and customization
    settings = Column(JSON, default=dict)  # Project-specific settings
    custom_fields = Column(JSON, default=dict)  # Custom field definitions
    
    # Flags
    is_template = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    is_public = Column(Boolean, default=False)  # For client access
    
    # Relationships
    organization = relationship("Organization", back_populates="projects")
    workspace = relationship("Workspace", back_populates="projects")
    owner = relationship("User", foreign_keys=[owner_id])
    customer = relationship("app.models.customer.Customer", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    invoices = relationship("ProjectInvoice", back_populates="project", cascade="all, delete-orphan")
    milestones = relationship("Milestone", back_populates="project", cascade="all, delete-orphan")
    recurring_templates = relationship("RecurringTaskTemplate", back_populates="project", cascade="all, delete-orphan")
    comments = relationship("ProjectComment", back_populates="project", cascade="all, delete-orphan")
    context_cards = relationship("ContextCard", back_populates="project", cascade="all, delete-orphan")
    handoff_summaries = relationship("HandoffSummary", back_populates="project", cascade="all, delete-orphan")
    decision_logs = relationship("DecisionLog", back_populates="project", cascade="all, delete-orphan")
    knowledge_articles = relationship("KnowledgeArticle", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project(name='{self.name}', status='{self.status}')>"


class ProjectMemberRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class ProjectMember(UUIDBaseModel):
    """Project membership model for user-project relationships"""
    __tablename__ = "project_members"
    
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(Enum(ProjectMemberRole), default=ProjectMemberRole.MEMBER)
    
    # Permissions
    can_edit_project = Column(Boolean, default=False)
    can_create_tasks = Column(Boolean, default=True)
    can_assign_tasks = Column(Boolean, default=False)
    can_delete_tasks = Column(Boolean, default=False)
    
    # Relationships
    project = relationship("Project", back_populates="members")
    user = relationship("User", back_populates="project_memberships")
    
    def __repr__(self):
        return f"<ProjectMember(project_id='{self.project_id}', user_id='{self.user_id}', role='{self.role}')>"
