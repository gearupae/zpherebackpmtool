from sqlalchemy import Column, String, Boolean, ForeignKey, Enum, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from typing import List
from .base import UUIDBaseModel


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    MEMBER = "MEMBER"
    CLIENT = "CLIENT"
    
    
class Permission(str, enum.Enum):
    # Project permissions
    CREATE_PROJECT = "create_project"
    EDIT_PROJECT = "edit_project"
    DELETE_PROJECT = "delete_project"
    VIEW_PROJECT = "view_project"
    
    # Task permissions
    CREATE_TASK = "create_task"
    EDIT_TASK = "edit_task"
    DELETE_TASK = "delete_task"
    ASSIGN_TASK = "assign_task"
    VIEW_TASK = "view_task"
    
    # Team permissions
    INVITE_MEMBER = "invite_member"
    REMOVE_MEMBER = "remove_member"
    MANAGE_ROLES = "manage_roles"
    VIEW_MEMBERS = "view_members"
    
    # File permissions
    UPLOAD_FILE = "upload_file"
    DELETE_FILE = "delete_file"
    VIEW_FILE = "view_file"
    
    # Comment permissions
    CREATE_COMMENT = "create_comment"
    EDIT_COMMENT = "edit_comment"
    DELETE_COMMENT = "delete_comment"
    
    # Analytics permissions
    VIEW_ANALYTICS = "view_analytics"
    VIEW_REPORTS = "view_reports"
    
    # Customer permissions
    CREATE_CUSTOMER = "create_customer"
    EDIT_CUSTOMER = "edit_customer"
    DELETE_CUSTOMER = "delete_customer"
    VIEW_CUSTOMER = "view_customer"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PENDING = "PENDING"
    SUSPENDED = "SUSPENDED"


class User(UUIDBaseModel):
    """User model with organization-based multi-tenancy"""
    __tablename__ = "users"
    
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
    
    # Organization and role
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)  # Nullable for super admins
    role = Column(Enum(UserRole), default=UserRole.MEMBER)
    
    # Profile information
    avatar_url = Column(String(500))
    timezone = Column(String(50), default="UTC")
    phone = Column(String(20))
    bio = Column(String(500))
    address = Column(String(255))
    
    # Preferences and settings
    preferences = Column(JSON, default=dict)  # User-specific preferences
    notification_settings = Column(JSON, default=dict)  # Notification preferences
    
    # Authentication tracking
    last_login = Column(DateTime(timezone=True))
    password_changed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="users")
    assigned_tasks = relationship("Task", foreign_keys="Task.assignee_id", back_populates="assignee")
    created_tasks = relationship("Task", foreign_keys="Task.created_by_id", back_populates="created_by")
    project_memberships = relationship("ProjectMember", back_populates="user")
    workspace_memberships = relationship("WorkspaceMember", back_populates="user")
    
    # Advanced PM Features Relationships
    dashboard_preferences = relationship("UserDashboardPreference", back_populates="user", uselist=False)
    workflow_preferences = relationship("UserWorkflowPreference", back_populates="user", uselist=False)
    
    # Role and permission relationships
    role_permissions = relationship("UserRolePermission", foreign_keys="UserRolePermission.user_id", back_populates="user", cascade="all, delete-orphan")
    team_memberships = relationship("TeamMember", foreign_keys="TeamMember.user_id", back_populates="user", cascade="all, delete-orphan")
    
    # Goals relationship
    goals = relationship("Goal", secondary="goal_members", back_populates="members")
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN
    
    @property
    def is_manager(self):
        return self.role in [UserRole.ADMIN, UserRole.MANAGER]

    @property
    def is_tenant(self):
        """True if the user belongs to a tenant (i.e., has an organization context).
        Platform admins typically have no organization_id.
        """
        return self.organization_id is not None
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission based on role and custom permissions"""
        # Super admin has all permissions
        if self.role == UserRole.ADMIN and not self.organization_id:
            return True
            
        # Role-based permissions
        role_permissions = self.get_role_permissions()
        if permission in role_permissions:
            return True
            
        # Custom user permissions (skip for now to avoid async issues)
        # TODO: Implement async permission checking
        # custom_permissions = [rp.permission for rp in self.role_permissions]
        # return permission in custom_permissions
        
        return False
    
    def get_role_permissions(self) -> List[Permission]:
        """Get default permissions for user role"""
        if self.role == UserRole.ADMIN:
            return [
                Permission.CREATE_PROJECT, Permission.EDIT_PROJECT, Permission.DELETE_PROJECT, Permission.VIEW_PROJECT,
                Permission.CREATE_TASK, Permission.EDIT_TASK, Permission.DELETE_TASK, Permission.ASSIGN_TASK, Permission.VIEW_TASK,
                Permission.INVITE_MEMBER, Permission.REMOVE_MEMBER, Permission.MANAGE_ROLES, Permission.VIEW_MEMBERS,
                Permission.UPLOAD_FILE, Permission.DELETE_FILE, Permission.VIEW_FILE,
                Permission.CREATE_COMMENT, Permission.EDIT_COMMENT, Permission.DELETE_COMMENT,
                Permission.VIEW_ANALYTICS, Permission.VIEW_REPORTS,
                Permission.CREATE_CUSTOMER, Permission.EDIT_CUSTOMER, Permission.DELETE_CUSTOMER, Permission.VIEW_CUSTOMER
            ]
        elif self.role == UserRole.MANAGER:
            return [
                Permission.CREATE_PROJECT, Permission.EDIT_PROJECT, Permission.VIEW_PROJECT,
                Permission.CREATE_TASK, Permission.EDIT_TASK, Permission.ASSIGN_TASK, Permission.VIEW_TASK,
                Permission.INVITE_MEMBER, Permission.VIEW_MEMBERS,
                Permission.UPLOAD_FILE, Permission.VIEW_FILE,
                Permission.CREATE_COMMENT, Permission.EDIT_COMMENT,
                Permission.VIEW_ANALYTICS,
                Permission.CREATE_CUSTOMER, Permission.EDIT_CUSTOMER, Permission.DELETE_CUSTOMER, Permission.VIEW_CUSTOMER
            ]
        elif self.role == UserRole.MEMBER:
            return [
                Permission.VIEW_PROJECT,
                Permission.CREATE_TASK, Permission.EDIT_TASK, Permission.VIEW_TASK,
                Permission.VIEW_MEMBERS,
                Permission.UPLOAD_FILE, Permission.VIEW_FILE,
                Permission.CREATE_COMMENT, Permission.EDIT_COMMENT,
                Permission.CREATE_CUSTOMER, Permission.EDIT_CUSTOMER, Permission.VIEW_CUSTOMER
            ]
        elif self.role == UserRole.CLIENT:
            return [
                Permission.VIEW_PROJECT,
                Permission.VIEW_TASK,
                Permission.VIEW_FILE,
                Permission.CREATE_COMMENT
            ]
        return []
    
    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role}')>"


class UserRolePermission(UUIDBaseModel):
    """Custom user permissions beyond role defaults"""
    __tablename__ = "user_role_permissions"
    
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    permission = Column(Enum(Permission), nullable=False)
    granted_by_id = Column(String, ForeignKey("users.id"))
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="role_permissions")
    granted_by = relationship("User", foreign_keys=[granted_by_id])
    
    def __repr__(self):
        return f"<UserRolePermission(user_id='{self.user_id}', permission='{self.permission}')>"


class Team(UUIDBaseModel):
    """Team model for organizing users into teams"""
    __tablename__ = "teams"
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Team settings
    is_default = Column(Boolean, default=False)  # Default team for new users
    is_active = Column(Boolean, default=True)
    settings = Column(JSON, default=dict)
    
    # Relationships
    organization = relationship("Organization")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Team(name='{self.name}')>"


class TeamMember(UUIDBaseModel):
    """Team membership model"""
    __tablename__ = "team_members"
    
    team_id = Column(String, ForeignKey("teams.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(String(50), default="member")  # team_lead, member
    
    # Relationships
    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")
    
    def __repr__(self):
        return f"<TeamMember(team_id='{self.team_id}', user_id='{self.user_id}')>"
