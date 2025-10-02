from sqlalchemy import Column, String, Text, Boolean, ForeignKey, JSON, Integer, Enum
from sqlalchemy.orm import relationship
import enum
from .base import UUIDBaseModel


class Workspace(UUIDBaseModel):
    """Workspace model for organizing projects by teams/clients within an organization"""
    __tablename__ = "workspaces"
    
    # Basic workspace info
    name = Column(String(255), nullable=False)
    description = Column(Text)
    slug = Column(String(100), nullable=False, index=True)
    
    # Organization relationship - workspaces belong to an organization
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Workspace settings
    color = Column(String(7), default="#3B82F6")  # Hex color for workspace identification
    icon = Column(String(50), default="folder")  # Icon name for workspace
    settings = Column(JSON, default=dict)  # Workspace-specific settings
    
    # Access control
    is_private = Column(Boolean, default=False)  # Private workspaces are invite-only
    is_archived = Column(Boolean, default=False)
    
    # Relationships
    organization = relationship("Organization", back_populates="workspaces")
    projects = relationship("Project", back_populates="workspace", cascade="all, delete-orphan")
    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Workspace(name='{self.name}', organization_id='{self.organization_id}')>"


class WorkspaceMemberRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class WorkspaceMember(UUIDBaseModel):
    """Workspace membership model for user-workspace relationships"""
    __tablename__ = "workspace_members"
    
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(Enum(WorkspaceMemberRole), default=WorkspaceMemberRole.MEMBER)
    
    # Permissions
    can_create_projects = Column(Boolean, default=True)
    can_invite_users = Column(Boolean, default=False)
    can_manage_workspace = Column(Boolean, default=False)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", back_populates="workspace_memberships")
    
    def __repr__(self):
        return f"<WorkspaceMember(workspace_id='{self.workspace_id}', user_id='{self.user_id}', role='{self.role}')>"
