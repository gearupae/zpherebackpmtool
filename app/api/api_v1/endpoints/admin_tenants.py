from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from datetime import datetime

from ....db.database import get_db
from ....models.user import User
from ....models.organization import Organization
from ....schemas.organization import OrganizationCreate
from ....schemas.user import UserCreate
from ....core.security import get_password_hash
# from ....schemas.organization import OrganizationInDB
from ...deps_tenant import require_platform_admin_master as require_platform_admin
from ....db.tenant_manager import tenant_manager

router = APIRouter()


@router.post("/")
async def create_tenant_organization(
    tenant_data: dict,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new tenant organization with admin user"""
    try:
        # Extract organization and admin user data
        org_name = tenant_data.get("name")
        org_slug = tenant_data.get("slug")
        admin_email = tenant_data.get("admin_email")
        admin_password = tenant_data.get("admin_password", "defaultpassword123")
        admin_first_name = tenant_data.get("admin_first_name", "Admin")
        admin_last_name = tenant_data.get("admin_last_name", "User")
        
        if not org_name or not org_slug or not admin_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization name, slug, and admin email are required"
            )
        
        # Check if organization slug already exists
        existing_org_result = await db.execute(
            select(Organization).where(Organization.slug == org_slug)
        )
        if existing_org_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization with this slug already exists"
            )
        
        # Check if admin email already exists
        existing_user_result = await db.execute(
            select(User).where(User.email == admin_email)
        )
        if existing_user_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Create organization
        new_org = Organization(
            name=org_name,
            slug=org_slug,
            description=tenant_data.get("description", f"{org_name} organization"),
            domain=tenant_data.get("domain"),
            is_active=True,
            subscription_tier=tenant_data.get("subscription_tier", "basic"),
            max_users=tenant_data.get("max_users", 50),
            max_projects=tenant_data.get("max_projects", 100),
            settings=tenant_data.get("settings", {}),
            branding=tenant_data.get("branding", {})
        )
        
        db.add(new_org)
        await db.flush()  # Get the organization ID
        
        # Create admin user for the organization
        hashed_password = get_password_hash(admin_password)
        admin_user = User(
            email=admin_email,
            username=org_slug + "_admin",
            first_name=admin_first_name,
            last_name=admin_last_name,
            hashed_password=hashed_password,
            is_active=True,
            is_verified=True,
            organization_id=new_org.id,
            role="MANAGER",  # Organization admin
            preferences={},
            notification_settings={}
        )
        
        db.add(admin_user)
        await db.commit()
        await db.refresh(new_org)
        await db.refresh(admin_user)
        
        # Immediately create tenant database and replicate org + admin user
        try:
            await tenant_manager.create_tenant_database(new_org.id)
            tenant_session = await tenant_manager.get_tenant_session(new_org.id)
            try:
                from sqlalchemy import select as sa_select
                # Replicate organization if not exists
                existing_org = await tenant_session.execute(sa_select(Organization).where(Organization.id == new_org.id))
                if not existing_org.scalar_one_or_none():
                    tenant_session.add(Organization(
                        id=new_org.id,
                        name=new_org.name,
                        slug=new_org.slug,
                        description=new_org.description,
                        domain=new_org.domain,
                        is_active=new_org.is_active,
                        subscription_tier=new_org.subscription_tier,
                        max_users=new_org.max_users,
                        max_projects=new_org.max_projects,
                        settings=new_org.settings,
                        branding=new_org.branding,
                    ))
                # Replicate admin user if not exists
                existing_tenant_user = await tenant_session.execute(sa_select(User).where(User.id == admin_user.id))
                if not existing_tenant_user.scalar_one_or_none():
                    tenant_session.add(User(
                        id=admin_user.id,
                        email=admin_user.email,
                        username=admin_user.username,
                        first_name=admin_user.first_name,
                        last_name=admin_user.last_name,
                        hashed_password=admin_user.hashed_password,
                        organization_id=new_org.id,
                        role=admin_user.role,
                        status=admin_user.status,
                        is_active=admin_user.is_active,
                        is_verified=admin_user.is_verified,
                        timezone=admin_user.timezone,
                        phone=admin_user.phone,
                        bio=admin_user.bio,
                        address=getattr(admin_user, "address", None),
                        preferences=admin_user.preferences,
                        notification_settings=admin_user.notification_settings,
                        last_login=admin_user.last_login,
                        password_changed_at=admin_user.password_changed_at,
                        avatar_url=getattr(admin_user, "avatar_url", None),
                    ))
                await tenant_session.commit()
            finally:
                await tenant_session.close()
        except Exception as te:
            # Non-fatal: log and continue so admin creation succeeds
            print(f"Tenant DB creation/replication warning for {new_org.id}: {te}")

        # Enable core modules for the new tenant automatically (TODO: when module system is implemented)

        return {
            "message": "Tenant organization created successfully",
            "organization": {
                "id": new_org.id,
                "name": new_org.name,
                "slug": new_org.slug,
                "description": new_org.description,
                "domain": new_org.domain,
                "subscription_tier": new_org.subscription_tier,
                "max_users": new_org.max_users,
                "max_projects": new_org.max_projects,
                "created_at": new_org.created_at.isoformat(),
                "is_active": new_org.is_active
            },
            "admin_user": {
                "id": admin_user.id,
                "email": admin_user.email,
                "username": admin_user.username,
                "first_name": admin_user.first_name,
                "last_name": admin_user.last_name,
                "role": admin_user.role
            },
            "enabled_modules": 0  # TODO: Update when module system is implemented
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tenant organization: {str(e)}"
        )


@router.get("/")
async def get_all_tenants(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by organization name or slug"),
) -> Any:
    """Get all tenant organizations with their statistics"""
    try:
        # Build the base query
        query = select(Organization)
        
        # Add search filter if provided
        if search:
            search_filter = or_(
                Organization.name.ilike(f"%{search}%"),
                Organization.slug.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
        
        # Add pagination
        query = query.offset(skip).limit(limit).order_by(Organization.created_at.desc())
        
        # Execute query
        result = await db.execute(query)
        organizations = result.scalars().all()
        
        # Get additional statistics for each organization
        tenant_list = []
        for org in organizations:
            # Count users in this organization
            user_count_query = select(func.count(User.id)).where(
                and_(User.organization_id == org.id, User.is_active == True)
            )
            user_count_result = await db.execute(user_count_query)
            user_count = user_count_result.scalar() or 0
            
            # Count projects (this would require tenant DB access in real implementation)
            # For now, we'll use a placeholder
            project_count = 0  # TODO: Implement cross-tenant project counting
            
            tenant_data = {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "subscription_status": "active",  # TODO: Implement subscription tracking
                "payment_status": "paid",  # TODO: Implement payment status from Stripe
                "created_at": org.created_at.isoformat(),
                "users_count": user_count,
                "projects_count": project_count,
                "is_active": org.is_active,
                "settings": org.settings,
            }
            tenant_list.append(tenant_data)
        
        return tenant_list
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenants: {str(e)}"
        )


@router.get("/{tenant_id}")
async def get_tenant_details(
    tenant_id: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get detailed information about a specific tenant"""
    try:
        # Get the organization
        query = select(Organization).where(Organization.id == tenant_id)
        result = await db.execute(query)
        org = result.scalar_one_or_none()
        
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Get users in this organization
        users_query = select(User).where(
            and_(User.organization_id == org.id, User.is_active == True)
        )
        users_result = await db.execute(users_query)
        users = users_result.scalars().all()
        
        # Count admins, managers, members
        role_counts = {
            "ADMIN": sum(1 for u in users if u.is_admin),
            "MANAGER": sum(1 for u in users if u.role == "MANAGER"),
            "MEMBER": sum(1 for u in users if u.role == "MEMBER"),
            "CLIENT": sum(1 for u in users if u.role == "CLIENT"),
        }
        
        # Get admin/manager user details
        admin_user = None
        for user in users:
            if user.role in ["MANAGER", "ADMIN"]:
                admin_user = {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "created_at": user.created_at.isoformat()
                }
                break
        
        tenant_details = {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "description": org.description,
            "domain": org.domain,
            "subscription_tier": org.subscription_tier,
            "max_users": org.max_users,
            "max_projects": org.max_projects,
            "subscription_status": "active",  # TODO: Implement subscription tracking
            "payment_status": "paid",  # TODO: Implement payment status from Stripe
            "created_at": org.created_at.isoformat(),
            "updated_at": org.updated_at.isoformat() if org.updated_at else None,
            "is_active": org.is_active,
            "settings": org.settings,
            "users_count": len(users),
            "role_distribution": role_counts,
            "admin_user": admin_user,
            "projects_count": 0,  # TODO: Implement cross-tenant project counting
            "storage_used": "0 MB",  # TODO: Implement storage tracking
            "last_active": None,  # TODO: Implement activity tracking
        }
        
        return tenant_details
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant details: {str(e)}"
        )


@router.put("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    tenant_data: dict,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update tenant organization information"""
    try:
        # Get existing tenant
        tenant_query = select(Organization).where(Organization.id == tenant_id)
        tenant_result = await db.execute(tenant_query)
        tenant = tenant_result.scalar_one_or_none()
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Update fields if provided
        if "name" in tenant_data:
            tenant.name = tenant_data["name"]
        if "slug" in tenant_data:
            # Check if new slug is unique
            if tenant_data["slug"] != tenant.slug:
                existing_slug_query = select(Organization).where(Organization.slug == tenant_data["slug"])
                existing_slug_result = await db.execute(existing_slug_query)
                if existing_slug_result.scalar_one_or_none():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Slug already exists"
                    )
            tenant.slug = tenant_data["slug"]
        if "description" in tenant_data:
            tenant.description = tenant_data["description"]
        if "domain" in tenant_data:
            tenant.domain = tenant_data["domain"]
        if "subscription_tier" in tenant_data:
            tenant.subscription_tier = tenant_data["subscription_tier"]
        if "max_users" in tenant_data:
            tenant.max_users = tenant_data["max_users"]
        if "max_projects" in tenant_data:
            tenant.max_projects = tenant_data["max_projects"]
        
        await db.commit()
        await db.refresh(tenant)
        
        return {
            "message": "Tenant updated successfully",
            "tenant": {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "description": tenant.description,
                "domain": tenant.domain,
                "subscription_tier": tenant.subscription_tier,
                "max_users": tenant.max_users,
                "max_projects": tenant.max_projects,
                "updated_at": tenant.updated_at
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tenant: {str(e)}"
        )


@router.put("/{tenant_id}/status")
async def update_tenant_status(
    tenant_id: str,
    is_active: bool,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Activate or suspend a tenant organization"""
    try:
        # Get the organization
        query = select(Organization).where(Organization.id == tenant_id)
        result = await db.execute(query)
        org = result.scalar_one_or_none()
        
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Update the status
        org.is_active = is_active
        org.updated_at = datetime.utcnow()
        
        await db.commit()
        
        return {
            "message": f"Tenant {'activated' if is_active else 'suspended'} successfully",
            "tenant_id": tenant_id,
            "is_active": is_active
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tenant status: {str(e)}"
        )


@router.post("/migrations/sync-all")
async def sync_all_tenant_schemas(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Synchronize schema changes across all tenant databases.

    This endpoint ensures new features (like columns) are applied for both existing and new tenants.
    Currently ensures:
    - users.address column exists (VARCHAR(255))
    """
    # Fetch all active tenant organizations from master DB
    result = await db.execute(select(Organization.id).where(Organization.is_active == True))
    org_ids = [row[0] for row in result.all()]

    applied = []
    skipped = []
    errors: list[dict] = []

    async def ensure_address_column(tenant_session: AsyncSession) -> bool:
        """Return True if we added the column, False if it already existed"""
        # Try Postgres information_schema first; fallback to SQLite PRAGMA
        try:
            check = await tenant_session.execute(
                text("SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='address'")
            )
            exists = check.scalar() is not None
        except Exception:
            # Likely SQLite
            try:
                pragma = await tenant_session.execute(text("PRAGMA table_info(users)"))
                rows = pragma.fetchall()
                exists = any((r[1] if isinstance(r, (list, tuple)) else getattr(r, 'name', '')) == 'address' for r in rows)
            except Exception:
                exists = False
        if exists:
            return False
        # Try Postgres-friendly alter, then SQLite fallback
        try:
            await tenant_session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS address VARCHAR(255)"))
        except Exception:
            # SQLite does not support IF NOT EXISTS with ADD COLUMN
            await tenant_session.execute(text("ALTER TABLE users ADD COLUMN address VARCHAR(255)"))
        return True

    for org_id in org_ids:
        try:
            # Ensure tenant DB exists and get a session
            await tenant_manager.create_tenant_database(org_id)
            tenant_session = await tenant_manager.get_tenant_session(org_id)
            try:
                changed = await ensure_address_column(tenant_session)
                await tenant_session.commit()
                if changed:
                    applied.append(org_id)
                else:
                    skipped.append(org_id)
            finally:
                await tenant_session.close()
        except Exception as e:
            errors.append({"tenant_id": org_id, "error": str(e)})

    return {
        "organizations_processed": len(org_ids),
        "address_column_added_to": applied,
        "skipped_already_present": skipped,
        "errors": errors,
    }

@router.get("/statistics/overview")
async def get_tenant_statistics(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get overall tenant statistics for the admin dashboard"""
    try:
        # Count total organizations
        total_orgs_query = select(func.count(Organization.id))
        total_orgs_result = await db.execute(total_orgs_query)
        total_orgs = total_orgs_result.scalar() or 0
        
        # Count active organizations
        active_orgs_query = select(func.count(Organization.id)).where(Organization.is_active == True)
        active_orgs_result = await db.execute(active_orgs_query)
        active_orgs = active_orgs_result.scalar() or 0
        
        # Count inactive organizations
        inactive_orgs = total_orgs - active_orgs
        
        # Count organizations created this month
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_this_month_query = select(func.count(Organization.id)).where(
            Organization.created_at >= current_month_start
        )
        new_this_month_result = await db.execute(new_this_month_query)
        new_this_month = new_this_month_result.scalar() or 0
        
        # Count total active users across all tenants
        total_users_query = select(func.count(User.id)).where(
            and_(User.is_active == True, User.is_admin == False)
        )
        total_users_result = await db.execute(total_users_query)
        total_users = total_users_result.scalar() or 0
        
        return {
            "organizations": {
                "total": total_orgs,
                "active": active_orgs,
                "inactive": inactive_orgs,
                "new_this_month": new_this_month,
            },
            "users": {
                "total_active": total_users,
                "average_per_org": round(total_users / total_orgs, 1) if total_orgs > 0 else 0,
            },
            "subscriptions": {
                "total": total_orgs,  # Assuming each org has one subscription
                "active": active_orgs,
                "trial": 0,  # TODO: Implement trial tracking
                "past_due": 0,  # TODO: Implement payment status tracking
                "conversion_rate": 85.5,  # TODO: Calculate real conversion rate
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant statistics: {str(e)}"
        )


@router.post("/{tenant_id}/users")
async def create_tenant_user(
    tenant_id: str,
    user_data: dict,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new user for a specific tenant"""
    try:
        # Verify tenant exists
        tenant_query = select(Organization).where(Organization.id == tenant_id)
        tenant_result = await db.execute(tenant_query)
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Check if user with email already exists
        email = user_data.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required"
            )
        
        existing_user_query = select(User).where(User.email == email)
        existing_user_result = await db.execute(existing_user_query)
        if existing_user_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Create new user
        hashed_password = get_password_hash(user_data.get("password", "defaultpassword123"))
        new_user = User(
            email=email,
            username=email.split("@")[0] + "_" + tenant.slug,
            first_name=user_data.get("first_name", "User"),
            last_name=user_data.get("last_name", "User"),
            hashed_password=hashed_password,
            is_active=True,
            is_verified=True,
            organization_id=tenant_id,
            role=user_data.get("role", "MEMBER"),
            preferences={},
            notification_settings={}
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        return {
            "message": "User created successfully",
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "username": new_user.username,
                "first_name": new_user.first_name,
                "last_name": new_user.last_name,
                "role": new_user.role,
                "organization_id": new_user.organization_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.put("/{tenant_id}/users/{user_email}/password")
async def reset_user_password(
    tenant_id: str,
    user_email: str,
    password_data: dict,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Reset password for a tenant user"""
    try:
        # Verify tenant exists
        tenant_query = select(Organization).where(Organization.id == tenant_id)
        tenant_result = await db.execute(tenant_query)
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Find user
        user_query = select(User).where(
            and_(User.email == user_email, User.organization_id == tenant_id)
        )
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in this tenant"
            )
        
        # Update password
        new_password = password_data.get("password", "defaultpassword123")
        user.hashed_password = get_password_hash(new_password)
        
        await db.commit()
        
        return {
            "message": "Password reset successfully",
            "user_email": user_email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset password: {str(e)}"
        )


# TODO: Re-enable when module system is implemented
# @router.get("/{tenant_id}/modules")
# async def get_tenant_modules(
#     tenant_id: str,
#     current_user: User = Depends(require_platform_admin),
#     db: AsyncSession = Depends(get_db),
# ) -> Any:
#     """Get all modules with their enablement status for a specific tenant"""
#     try:
#         # Verify tenant exists
#         tenant_query = select(Organization).where(Organization.id == tenant_id)
#         tenant_result = await db.execute(tenant_query)
#         tenant = tenant_result.scalar_one_or_none()
#         if not tenant:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Tenant not found"
#             )
#         
#         # Get all modules with tenant enablement status
#         # from ....models.module import Module, TenantModule  # Module model doesn't exist
#         query = select(
#             Module,
#             TenantModule.is_enabled,
#             TenantModule.id.label('tenant_module_id')
#         ).outerjoin(
#             TenantModule, 
#             and_(Module.id == TenantModule.module_id, TenantModule.tenant_id == tenant_id)
#         ).order_by(Module.is_core.desc(), Module.category, Module.name)
#         
#         result = await db.execute(query)
#         module_data = result.all()
#         
#         modules = []
#         for row in module_data:
#             module_info = {
#                 "id": row.Module.id,
#                 "name": row.Module.name,
#                 "description": row.Module.description,
#                 "category": row.Module.category,
#                 "price_per_month": row.Module.price_per_month,
#                 "is_core": row.Module.is_core,
#                 "is_available": row.Module.is_available,
#                 "features": row.Module.features,
#                 "is_enabled_for_tenant": row.is_enabled if row.is_enabled is not None else False,
#                 "tenant_module_id": row.tenant_module_id
#             }
#             modules.append(module_info)
#         
#         return {
#             "tenant_id": tenant_id,
#             "tenant_name": tenant.name,
#             "modules": modules
#         }
#         
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to fetch tenant modules: {str(e)}"
#         )
    pass  # TODO: Implement when module system is ready


# TODO: Re-enable when module system is implemented
# @router.post("/{tenant_id}/modules/{module_id}/toggle")
# async def toggle_tenant_module(
#     tenant_id: str,
#     module_id: str,
#     current_user: User = Depends(require_platform_admin),
#     db: AsyncSession = Depends(get_db),
# ) -> Any:
#     """Toggle a module on/off for a specific tenant"""
#    try:
#        # Verify tenant exists
#        tenant_query = select(Organization).where(Organization.id == tenant_id)
#        tenant_result = await db.execute(tenant_query)
#        tenant = tenant_result.scalar_one_or_none()
#        if not tenant:
#            raise HTTPException(
#                status_code=status.HTTP_404_NOT_FOUND,
#                detail="Tenant not found"
#            )
#        
#        # Verify module exists
#        # from ....models.module import Module, TenantModule  # Module model doesn't exist
#        module_query = select(Module).where(Module.id == module_id)
#        module_result = await db.execute(module_query)
#        module = module_result.scalar_one_or_none()
#        if not module:
#            raise HTTPException(
#                status_code=status.HTTP_404_NOT_FOUND,
#                detail="Module not found"
#            )
#        
#        if module.is_core:
#            raise HTTPException(
#                status_code=status.HTTP_400_BAD_REQUEST,
#                detail="Core modules cannot be disabled"
#            )
#        
#        if not module.is_available:
#            raise HTTPException(
#                status_code=status.HTTP_400_BAD_REQUEST,
#                detail="Module is not available for activation"
#            )
#        
#        # Check current status
#        tenant_module_query = select(TenantModule).where(
#            and_(TenantModule.tenant_id == tenant_id, TenantModule.module_id == module_id)
#        )
#        tenant_module_result = await db.execute(tenant_module_query)
#        tenant_module = tenant_module_result.scalar_one_or_none()
#        
#        if tenant_module:
#            # Toggle existing status
#            new_status = not tenant_module.is_enabled
#            tenant_module.is_enabled = new_status
#            tenant_module.updated_at = datetime.utcnow()
#            if new_status:
#                tenant_module.enabled_at = datetime.utcnow()
#                tenant_module.disabled_at = None
#            else:
#                tenant_module.disabled_at = datetime.utcnow()
#        else:
#            # Create new enabled relationship
#            new_status = True
#            tenant_module = TenantModule(
#                tenant_id=tenant_id,
#                module_id=module_id,
#                is_enabled=True
#            )
#            db.add(tenant_module)
#        
#        await db.commit()
#        
#        return {
#            "message": f"Module '{module.name}' {'enabled' if new_status else 'disabled'} for tenant '{tenant.name}'",
#            "tenant_id": tenant_id,
#            "module_id": module_id,
#            "is_enabled": new_status,
#            "module_name": module.name,
#            "tenant_name": tenant.name
#        }
#        
#    except HTTPException:
#        raise
#    except Exception as e:
#        await db.rollback()
#        raise HTTPException(
#            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#            detail=f"Failed to toggle module: {str(e)}"
#        )
