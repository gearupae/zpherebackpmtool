from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import uuid

from ....db.database import get_db
from ....db.tenant_manager import tenant_manager
from ....models.user import User, UserRole
from ....models.project import Project, ProjectMember, ProjectMemberRole
from ....models.organization import Organization
from ...deps import get_current_active_user
from ...deps_tenant import get_tenant_db
from ....schemas.team import (
    TeamMemberCreate,
    TeamMemberUpdate,
    TeamMember,
    ProjectMemberCreate,
    ProjectMemberUpdate,
    ProjectMemberResponse,
    InviteMemberRequest
)

router = APIRouter()


@router.get("/members", response_model=List[TeamMember])
async def get_team_members(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get all team members in the current user's organization"""
    
    # Get all users in the same organization
    result = await db.execute(
        select(User).where(User.organization_id == current_user.organization_id)
    )
    users = result.scalars().all()
    
    # Convert to team member format
    team_members = []
    for user in users:
        team_members.append(TeamMember(
            id=user.id,
            email=user.email,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            role=user.role,
            status=user.status,
            is_active=user.is_active,
            avatar_url=user.avatar_url,
            timezone=user.timezone,
            phone=user.phone,
            bio=user.bio,
            address=getattr(user, 'address', None),
            last_login=user.last_login,
            created_at=user.created_at
        ))
    
    return team_members


@router.post("/members", response_model=TeamMember, status_code=status.HTTP_201_CREATED)
async def create_team_member(
    member_data: TeamMemberCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new team member (Admin/Manager only)"""
    
    # Check if user has permission to create team members
    if not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can create team members"
        )
    
    # Check if email already exists
    existing_user = await db.execute(
        select(User).where(User.email == member_data.email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Check if username already exists
    existing_username = await db.execute(
        select(User).where(User.username == member_data.username)
    )
    if existing_username.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create new user
    from ....core.security import get_password_hash
    new_user = User(
        id=str(uuid.uuid4()),
        email=member_data.email,
        username=member_data.username,
        first_name=member_data.first_name,
        last_name=member_data.last_name,
        hashed_password=get_password_hash(member_data.password),
        organization_id=current_user.organization_id,
        role=member_data.role or UserRole.MEMBER,
        status=member_data.status or "pending",
        timezone=member_data.timezone or "UTC",
        phone=member_data.phone,
        bio=member_data.bio,
        address=getattr(member_data, 'address', None)
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Replicate user to tenant DB
    try:
        from sqlalchemy import select as sa_select
        tenant_session = await tenant_manager.get_tenant_session(current_user.organization_id)
        try:
            existing = await tenant_session.execute(sa_select(User).where(User.id == new_user.id))
            if not existing.scalar_one_or_none():
                tenant_session.add(User(
                    id=new_user.id,
                    email=new_user.email,
                    username=new_user.username,
                    first_name=new_user.first_name,
                    last_name=new_user.last_name,
                    hashed_password=new_user.hashed_password,
                    organization_id=new_user.organization_id,
                    role=new_user.role,
                    status=new_user.status,
                    is_active=new_user.is_active,
                    is_verified=new_user.is_verified,
                    timezone=new_user.timezone,
                    phone=new_user.phone,
                    bio=new_user.bio,
                    address=getattr(new_user, 'address', None)
                ))
                await tenant_session.commit()
        finally:
            await tenant_session.close()
    except Exception as te:
        import traceback
        print(f"Tenant user replication warning: {te}\n{traceback.format_exc()}")
    
    return TeamMember(
        id=new_user.id,
        email=new_user.email,
        username=new_user.username,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        full_name=new_user.full_name,
        role=new_user.role,
        status=new_user.status,
        is_active=new_user.is_active,
        avatar_url=new_user.avatar_url,
        timezone=new_user.timezone,
        phone=new_user.phone,
        bio=new_user.bio,
        address=getattr(new_user, 'address', None),
        last_login=new_user.last_login,
        created_at=new_user.created_at
    )


@router.get("/projects/{project_id}/members", response_model=List[ProjectMemberResponse])
async def get_project_members(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get all members of a specific project"""
    
    # Check if project exists and user has access
    project_result = await db.execute(
        select(Project).where(
            and_(
                Project.id == project_id,
                Project.organization_id == current_user.organization_id
            )
        )
    )
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Get project members
    members_result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    )
    members = members_result.scalars().all()
    
    # Convert to response format
    project_members = []
    for member in members:
        user_result = await db.execute(select(User).where(User.id == member.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            project_members.append(ProjectMemberResponse(
                id=member.id,
                project_id=member.project_id,
                user_id=member.user_id,
                role=member.role,
                can_edit_project=member.can_edit_project,
                can_create_tasks=member.can_create_tasks,
                can_assign_tasks=member.can_assign_tasks,
                can_delete_tasks=member.can_delete_tasks,
                user=TeamMember(
                    id=user.id,
                    email=user.email,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    full_name=user.full_name,
                    role=user.role,
                    status=user.status,
                    is_active=user.is_active,
                    avatar_url=user.avatar_url,
                    timezone=user.timezone,
                    phone=user.phone,
                    bio=user.bio,
                    address=getattr(user, 'address', None),
                    last_login=user.last_login,
                    created_at=user.created_at
                ),
                created_at=member.created_at
            ))
    
    return project_members


@router.post("/projects/{project_id}/members", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_project_member(
    project_id: str,
    member_data: ProjectMemberCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Add a member to a project"""
    
    # Check if project exists and user has access
    project_result = await db.execute(
        select(Project).where(
            and_(
                Project.id == project_id,
                Project.organization_id == current_user.organization_id
            )
        )
    )
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check if user has permission to add members
    if not current_user.is_manager and project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owners and managers can add members"
        )
    
    # Check if user exists and is in the same organization
    user_result = await db.execute(
        select(User).where(
            and_(
                User.id == member_data.user_id,
                User.organization_id == current_user.organization_id
            )
        )
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or not in the same organization"
        )
    
    # Check if user is already a member
    existing_member = await db.execute(
        select(ProjectMember).where(
            and_(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == member_data.user_id
            )
        )
    )
    if existing_member.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this project"
        )
    
    # Create project membership
    project_member = ProjectMember(
        id=str(uuid.uuid4()),
        project_id=project_id,
        user_id=member_data.user_id,
        role=member_data.role or ProjectMemberRole.MEMBER,
        can_edit_project=member_data.can_edit_project or False,
        can_create_tasks=member_data.can_create_tasks or True,
        can_assign_tasks=member_data.can_assign_tasks or False,
        can_delete_tasks=member_data.can_delete_tasks or False
    )
    
    db.add(project_member)
    await db.commit()
    await db.refresh(project_member)
    
    return ProjectMemberResponse(
        id=project_member.id,
        project_id=project_member.project_id,
        user_id=project_member.user_id,
        role=project_member.role,
        can_edit_project=project_member.can_edit_project,
        can_create_tasks=project_member.can_create_tasks,
        can_assign_tasks=project_member.can_assign_tasks,
        can_delete_tasks=project_member.can_delete_tasks,
        user=TeamMember(
            id=user.id,
            email=user.email,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            role=user.role,
            status=user.status,
            is_active=user.is_active,
            avatar_url=user.avatar_url,
            timezone=user.timezone,
            phone=user.phone,
            bio=user.bio,
            last_login=user.last_login,
            created_at=user.created_at
        ),
        created_at=project_member.created_at
    )


@router.put("/projects/{project_id}/members/{member_id}", response_model=ProjectMemberResponse)
async def update_project_member(
    project_id: str,
    member_id: str,
    member_data: ProjectMemberUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update project member permissions"""
    
    # Check if project exists and user has access
    project_result = await db.execute(
        select(Project).where(
            and_(
                Project.id == project_id,
                Project.organization_id == current_user.organization_id
            )
        )
    )
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check if user has permission to update members
    if not current_user.is_manager and project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owners and managers can update members"
        )
    
    # Get project member
    member_result = await db.execute(
        select(ProjectMember).where(
            and_(
                ProjectMember.id == member_id,
                ProjectMember.project_id == project_id
            )
        )
    )
    member = member_result.scalar_one_or_none()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project member not found"
        )
    
    # Update member data
    if member_data.role is not None:
        member.role = member_data.role
    if member_data.can_edit_project is not None:
        member.can_edit_project = member_data.can_edit_project
    if member_data.can_create_tasks is not None:
        member.can_create_tasks = member_data.can_create_tasks
    if member_data.can_assign_tasks is not None:
        member.can_assign_tasks = member_data.can_assign_tasks
    if member_data.can_delete_tasks is not None:
        member.can_delete_tasks = member_data.can_delete_tasks
    
    await db.commit()
    await db.refresh(member)
    
    # Get user info for response
    user_result = await db.execute(select(User).where(User.id == member.user_id))
    user = user_result.scalar_one_or_none()
    
    return ProjectMemberResponse(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role,
        can_edit_project=member.can_edit_project,
        can_create_tasks=member.can_create_tasks,
        can_assign_tasks=member.can_assign_tasks,
        can_delete_tasks=member.can_delete_tasks,
        user=TeamMember(
            id=user.id,
            email=user.email,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            role=user.role,
            status=user.status,
            is_active=user.is_active,
            avatar_url=user.avatar_url,
            timezone=user.timezone,
            phone=user.phone,
            bio=user.bio,
            address=getattr(user, 'address', None),
            last_login=user.last_login,
            created_at=user.created_at
        ),
        created_at=member.created_at
    )


@router.delete("/projects/{project_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_member(
    project_id: str,
    member_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> None:
    """Remove a member from a project"""
    
    # Check if project exists and user has access
    project_result = await db.execute(
        select(Project).where(
            and_(
                Project.id == project_id,
                Project.organization_id == current_user.organization_id
            )
        )
    )
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check if user has permission to remove members
    if not current_user.is_manager and project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owners and managers can remove members"
        )
    
    # Get project member
    member_result = await db.execute(
        select(ProjectMember).where(
            and_(
                ProjectMember.id == member_id,
                ProjectMember.project_id == project_id
            )
        )
    )
    member = member_result.scalar_one_or_none()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project member not found"
        )
    
    # Don't allow removing the project owner
    if member.role == ProjectMemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove project owner"
        )
    
    # Remove member
    await db.delete(member)
    await db.commit()
