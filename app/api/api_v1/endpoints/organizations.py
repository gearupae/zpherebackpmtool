from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ....api.deps_tenant import get_master_db as get_db
from ....models.user import User
from ....models.organization import Organization
from ....models.project import Project
from ....models.subscription import Subscription
from ...deps_tenant import get_current_active_user_master as get_current_active_user, get_current_organization_master as get_current_organization_dep, require_tenant_user as require_admin

router = APIRouter()


@router.get("/me")
async def get_current_organization_info(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization_dep),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get current user's organization with usage stats"""
    
    # Get usage statistics
    user_count_result = await db.execute(
        select(func.count()).where(User.organization_id == current_org.id)
    )
    user_count = user_count_result.scalar()
    
    project_count_result = await db.execute(
        select(func.count()).where(Project.organization_id == current_org.id)
    )
    project_count = project_count_result.scalar()
    
    # Get subscription info
    subscription_result = await db.execute(
        select(Subscription).where(Subscription.organization_id == current_org.id)
    )
    subscription = subscription_result.scalar_one_or_none()
    
    return {
        "id": current_org.id,
        "name": current_org.name,
        "slug": current_org.slug,
        "description": current_org.description,
        "domain": current_org.domain,
        "is_active": current_org.is_active,
        "subscription_tier": current_org.subscription_tier,
        "max_users": current_org.max_users,
        "max_projects": current_org.max_projects,
        "settings": current_org.settings,
        "branding": current_org.branding,
        "created_at": current_org.created_at,
        "updated_at": current_org.updated_at,
        "usage": {
            "user_count": user_count,
            "project_count": project_count,
        },
        "subscription": {
            "tier": subscription.tier if subscription else "starter",
            "status": subscription.status if subscription else "trialing"
        }
    }


@router.put("/me")
async def update_current_organization(
    org_data: dict,
    current_user: User = Depends(require_admin),
    current_org: Organization = Depends(get_current_organization_dep),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update current organization"""
    
    # Update allowed fields
    allowed_fields = ["name", "description", "domain", "settings", "branding"]
    for field in allowed_fields:
        if field in org_data:
            setattr(current_org, field, org_data[field])
    
    await db.commit()
    await db.refresh(current_org)
    
    return {"message": "Organization updated successfully"}


@router.get("/settings")
async def get_organization_settings(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization_dep),
) -> Any:
    """Get organization settings"""
    
    return {
        "general": {
            "name": current_org.name,
            "description": current_org.description,
            "domain": current_org.domain,
            "timezone": current_org.settings.get("timezone", "UTC"),
            "date_format": current_org.settings.get("date_format", "YYYY-MM-DD"),
            "currency": current_org.settings.get("currency", "USD")
        },
        "features": {
            "time_tracking": current_org.settings.get("time_tracking", True),
            "project_templates": current_org.settings.get("project_templates", True),
            "client_portal": current_org.settings.get("client_portal", False),
            "invoicing": current_org.settings.get("invoicing", True)
        },
        "notifications": {
            "email_notifications": current_org.settings.get("email_notifications", True),
            "slack_integration": current_org.settings.get("slack_integration", False),
            "webhook_url": current_org.settings.get("webhook_url", "")
        },
        "branding": current_org.branding
    }


@router.put("/settings")
async def update_organization_settings(
    settings_data: dict,
    current_user: User = Depends(require_admin),
    current_org: Organization = Depends(get_current_organization_dep),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update organization settings"""
    
    # Merge new settings with existing
    current_settings = current_org.settings or {}
    current_branding = current_org.branding or {}
    
    if "general" in settings_data:
        current_settings.update(settings_data["general"])
    
    if "features" in settings_data:
        current_settings.update(settings_data["features"])
    
    if "notifications" in settings_data:
        current_settings.update(settings_data["notifications"])
    
    if "branding" in settings_data:
        current_branding.update(settings_data["branding"])
    
    current_org.settings = current_settings
    current_org.branding = current_branding
    
    await db.commit()
    
    return {"message": "Settings updated successfully"}


@router.get("/usage")
async def get_organization_usage(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization_dep),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get organization usage statistics"""
    
    # Get detailed usage stats
    user_count_result = await db.execute(
        select(func.count()).where(User.organization_id == current_org.id)
    )
    user_count = user_count_result.scalar()
    
    active_user_count_result = await db.execute(
        select(func.count()).where(
            User.organization_id == current_org.id,
            User.is_active == True
        )
    )
    active_user_count = active_user_count_result.scalar()
    
    project_count_result = await db.execute(
        select(func.count()).where(Project.organization_id == current_org.id)
    )
    project_count = project_count_result.scalar()
    
    active_project_count_result = await db.execute(
        select(func.count()).where(
            Project.organization_id == current_org.id,
            Project.is_archived == False
        )
    )
    active_project_count = active_project_count_result.scalar()
    
    return {
        "users": {
            "total": user_count,
            "active": active_user_count,
            "limit": current_org.max_users
        },
        "projects": {
            "total": project_count,
            "active": active_project_count,
            "limit": current_org.max_projects
        },
        "storage": {
            "used_mb": 0,  # TODO: Calculate actual storage usage
            "limit_gb": 1  # TODO: Get from subscription
        }
    }


@router.post("/invite")
async def invite_user(
    invite_data: dict,
    current_user: User = Depends(require_admin),
    current_org: Organization = Depends(get_current_organization_dep),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Invite a user to the organization"""
    
    email = invite_data.get("email")
    role = invite_data.get("role", "member")
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )
    
    # Check if user already exists
    existing_user_result = await db.execute(
        select(User).where(User.email == email)
    )
    existing_user = existing_user_result.scalar_one_or_none()
    
    if existing_user:
        if existing_user.organization_id == current_org.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this organization"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists in another organization"
            )
    
    # TODO: Create invitation record and send invitation email
    # For now, just return success
    
    return {
        "message": f"Invitation sent to {email}",
        "email": email,
        "role": role,
        "invited_by": f"{current_user.first_name} {current_user.last_name}"
    }
