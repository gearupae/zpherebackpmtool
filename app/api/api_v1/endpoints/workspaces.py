from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ....api.deps_tenant import get_tenant_db as get_db
from ....api.deps_tenant import get_current_active_user_master as get_current_active_user, get_current_organization_master as get_current_organization
from ....models.user import User
from ....models.organization import Organization
from ....models.workspace import Workspace, WorkspaceMember, WorkspaceMemberRole
from ....schemas.workspace import (
    WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse,
    WorkspaceMemberCreate, WorkspaceMemberResponse
)

router = APIRouter()


@router.get("/", response_model=List[WorkspaceResponse])
async def get_workspaces(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get all workspaces for the current organization"""
    
    # Get workspaces where user has access
    query = select(Workspace).where(
        and_(
            Workspace.organization_id == current_org.id,
            Workspace.is_archived == False
        )
    ).offset(skip).limit(limit)
    
    result = await db.execute(query)
    workspaces = result.scalars().all()
    
    return workspaces


@router.post("/", response_model=WorkspaceResponse)
async def create_workspace(
    workspace_in: WorkspaceCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new workspace"""
    
    # Create workspace
    workspace = Workspace(
        name=workspace_in.name,
        description=workspace_in.description,
        slug=workspace_in.slug or workspace_in.name.lower().replace(" ", "-"),
        organization_id=current_org.id,
        color=workspace_in.color,
        icon=workspace_in.icon,
        is_private=workspace_in.is_private,
        settings=workspace_in.settings or {}
    )
    
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    
    # Add creator as admin
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role=WorkspaceMemberRole.ADMIN,
        can_create_projects=True,
        can_invite_users=True,
        can_manage_workspace=True
    )
    
    db.add(member)
    await db.commit()
    
    return workspace


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get workspace by ID"""
    
    query = select(Workspace).where(
        and_(
            Workspace.id == workspace_id,
            Workspace.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    workspace = result.scalar_one_or_none()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return workspace


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    workspace_in: WorkspaceUpdate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update workspace"""
    
    query = select(Workspace).where(
        and_(
            Workspace.id == workspace_id,
            Workspace.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    workspace = result.scalar_one_or_none()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Update workspace fields
    for field, value in workspace_in.dict(exclude_unset=True).items():
        setattr(workspace, field, value)
    
    await db.commit()
    await db.refresh(workspace)
    
    return workspace


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Delete (archive) workspace"""
    
    query = select(Workspace).where(
        and_(
            Workspace.id == workspace_id,
            Workspace.organization_id == current_org.id
        )
    )
    
    result = await db.execute(query)
    workspace = result.scalar_one_or_none()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Archive instead of delete to preserve data
    workspace.is_archived = True
    await db.commit()
    
    return {"message": "Workspace archived successfully"}


@router.get("/{workspace_id}/members", response_model=List[WorkspaceMemberResponse])
async def get_workspace_members(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get workspace members"""
    
    # Verify workspace access
    workspace_query = select(Workspace).where(
        and_(
            Workspace.id == workspace_id,
            Workspace.organization_id == current_org.id
        )
    )
    
    workspace_result = await db.execute(workspace_query)
    workspace = workspace_result.scalar_one_or_none()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Get members
    members_query = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id
    )
    
    members_result = await db.execute(members_query)
    members = members_result.scalars().all()
    
    return members


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberResponse)
async def add_workspace_member(
    workspace_id: str,
    member_in: WorkspaceMemberCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Add member to workspace"""
    
    # Verify workspace access
    workspace_query = select(Workspace).where(
        and_(
            Workspace.id == workspace_id,
            Workspace.organization_id == current_org.id
        )
    )
    
    workspace_result = await db.execute(workspace_query)
    workspace = workspace_result.scalar_one_or_none()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Check if user is already a member
    existing_member_query = select(WorkspaceMember).where(
        and_(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_in.user_id
        )
    )
    
    existing_result = await db.execute(existing_member_query)
    existing_member = existing_result.scalar_one_or_none()
    
    if existing_member:
        raise HTTPException(status_code=400, detail="User is already a member of this workspace")
    
    # Create membership
    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=member_in.user_id,
        role=member_in.role,
        can_create_projects=member_in.can_create_projects,
        can_invite_users=member_in.can_invite_users,
        can_manage_workspace=member_in.can_manage_workspace
    )
    
    db.add(member)
    await db.commit()
    await db.refresh(member)
    
    return member
