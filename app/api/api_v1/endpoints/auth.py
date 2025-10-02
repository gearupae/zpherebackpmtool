from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ....api.deps_tenant import get_master_db as get_db
from ....core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    verify_refresh_token,
    get_password_hash
)
from ....core.config import settings
from ....models.user import User, UserRole, UserStatus
from ....models.organization import Organization
from ....db.tenant_manager import tenant_manager
from ....schemas.auth import Token, LoginRequest, RefreshTokenRequest, ChangePasswordRequest
from pydantic import BaseModel
from typing import Optional
from ....schemas.user import UserCreate, UserRegister, User as UserSchema
import uuid
from ...deps import get_current_active_user

router = APIRouter()

class GoogleLoginRequest(BaseModel):
    id_token: str
    organization_name: Optional[str] = None


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """OAuth2 compatible token login, get an access token for future requests"""
    
    # Get user by email
    result = await db.execute(
        select(User).where(User.email == login_data.email)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Check if user's organization is active (for non-admin users)
    if user.organization_id and user.role != 'ADMIN':
        org_result = await db.execute(
            select(Organization).where(Organization.id == user.organization_id)
        )
        organization = org_result.scalar_one_or_none()
        
        if not organization or not organization.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization is suspended. Please contact support."
            )
    
    # Update last login
    from datetime import datetime
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Create tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.username, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(subject=user.username)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Refresh access token using refresh token"""
    
    username = verify_refresh_token(refresh_data.refresh_token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    # Get user
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Create new tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.username, expires_delta=access_token_expires
    )
    new_refresh_token = create_refresh_token(subject=user.username)
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.post("/google", response_model=Token)
async def google_login(
    payload: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Google OAuth login/signup using ID token."""
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google login not available: missing google-auth library")
    
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google login not configured")
    
    try:
        # Verify the token
        req = google_requests.Request()
        idinfo = google_id_token.verify_oauth2_token(payload.id_token, req, settings.GOOGLE_CLIENT_ID)
        email = idinfo.get("email")
        given_name = idinfo.get("given_name") or "User"
        family_name = idinfo.get("family_name") or ""
        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Google token")
        
        # Find existing user
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        # If no user, create org and user (tenant admin)
        if not user:
            import uuid
            org_id = str(uuid.uuid4())
            org_name = payload.organization_name or (email.split("@")[0] + " org")
            slug_base = org_name.lower().replace(" ", "-").replace("_", "-")
            org = Organization(
                id=org_id,
                name=org_name,
                slug=slug_base,
                is_active=True,
                subscription_tier="starter",
                max_users=3,
                max_projects=5
            )
            db.add(org)
            
            # Unique username from email prefix
            username = email.split('@')[0]
            from sqlalchemy import select as sa_select
            counter = 1
            base_username = username
            while True:
                res_u = await db.execute(sa_select(User).where(User.username == username))
                if not res_u.scalar_one_or_none():
                    break
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                username=username,
                first_name=given_name,
                last_name=family_name,
                hashed_password=get_password_hash(str(uuid.uuid4())),  # random
                organization_id=org_id,
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
                status=UserStatus.ACTIVE
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
            # Best-effort tenant DB creation and replication similar to register
            try:
                created = await tenant_manager.create_tenant_database(org_id)
                tenant_session = None
                if created:
                    tenant_session = await tenant_manager.get_tenant_session(org_id)
                else:
                    tenant_session = None
                try:
                    if tenant_session:
                        # Replicate org
                        existing_org = await tenant_session.execute(sa_select(Organization).where(Organization.id == org_id))
                        if not existing_org.scalar_one_or_none():
                            tenant_session.add(Organization(
                                id=org_id,
                                name=org.name,
                                slug=org.slug,
                                description=org.description,
                                domain=org.domain,
                                is_active=org.is_active,
                                subscription_tier=org.subscription_tier,
                                max_users=org.max_users,
                                max_projects=org.max_projects,
                                settings=org.settings,
                                branding=org.branding
                            ))
                        # Replicate user
                        existing_tu = await tenant_session.execute(sa_select(User).where(User.id == user.id))
                        if not existing_tu.scalar_one_or_none():
                            tenant_session.add(User(
                                id=user.id,
                                email=user.email,
                                username=user.username,
                                first_name=user.first_name,
                                last_name=user.last_name,
                                hashed_password=user.hashed_password,
                                organization_id=org_id,
                                role=user.role,
                                status=user.status,
                                is_active=user.is_active,
                                is_verified=user.is_verified,
                            ))
                        await tenant_session.commit()
                        await tenant_session.close()
                except Exception:
                    pass
            except Exception:
                pass
        else:
            # Ensure active
            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
        
        # Issue tokens
        access_token = create_access_token(subject=user.username, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        refresh_token = create_refresh_token(subject=user.username)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Google login failed: {str(e)}")


@router.post("/register", response_model=UserSchema)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Register a new user with organization"""
    
    # Check if user already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    try:
        # Create organization first
        org_id = str(uuid.uuid4())
        organization = Organization(
            id=org_id,
            name=user_data.organization_name,
            slug=user_data.organization_name.lower().replace(' ', '-').replace('_', '-'),
            is_active=True,
            subscription_tier="starter",
            max_users=3,
            max_projects=5
        )
        
        db.add(organization)
        await db.flush()  # Flush to get the organization ID
        
        # Generate username from email
        username = user_data.email.split('@')[0]
        counter = 1
        original_username = username
        
        # Ensure username is unique
        while True:
            result = await db.execute(
                select(User).where(User.username == username)
            )
            if not result.scalar_one_or_none():
                break
            username = f"{original_username}{counter}"
            counter += 1
        
        # Create new user
        hashed_password = get_password_hash(user_data.password)
        user_id = str(uuid.uuid4())
        
        db_user = User(
            id=user_id,
            email=user_data.email,
            username=username,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            hashed_password=hashed_password,
            organization_id=org_id,
            role=UserRole.ADMIN,  # First user is admin of their organization
            is_active=True,
            is_verified=False,
            status=UserStatus.ACTIVE
        )
        
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

        # Send welcome email (best-effort)
        try:
            from ....services.email_service import send_welcome_email
            send_welcome_email(db_user.email, organization.name)
        except Exception:
            pass
        
        # Create tenant database and replicate org + user into tenant DB
        try:
            created = await tenant_manager.create_tenant_database(org_id)
            tenant_session = None
            if created:
                tenant_session = await tenant_manager.get_tenant_session(org_id)
            else:
                tenant_session = None
            try:
                # Replicate organization if not exists
                from sqlalchemy import select as sa_select
                if tenant_session:
                    existing_org = await tenant_session.execute(sa_select(Organization).where(Organization.id == org_id))
                    if not existing_org.scalar_one_or_none():
                        tenant_session.add(Organization(
                        id=org_id,
                        name=organization.name,
                        slug=organization.slug,
                        description=organization.description,
                        domain=organization.domain,
                        is_active=organization.is_active,
                        subscription_tier=organization.subscription_tier,
                        max_users=organization.max_users,
                        max_projects=organization.max_projects,
                        settings=organization.settings,
                        branding=organization.branding
                    ))
                # Replicate user if not exists
                if tenant_session:
                    existing_tenant_user = await tenant_session.execute(sa_select(User).where(User.id == user_id))
                    if not existing_tenant_user.scalar_one_or_none():
                        tenant_session.add(User(
                        id=user_id,
                        email=db_user.email,
                        username=db_user.username,
                        first_name=db_user.first_name,
                        last_name=db_user.last_name,
                        hashed_password=db_user.hashed_password,
                        organization_id=org_id,
                        role=db_user.role,
                        status=db_user.status,
                        is_active=db_user.is_active,
                        is_verified=db_user.is_verified,
                        timezone=db_user.timezone
                    ))
                if tenant_session:
                    await tenant_session.commit()
            finally:
                if tenant_session:
                    await tenant_session.close()
        except Exception as te:
            # Log and continue; tenant replication should not block registration
            import traceback
            print(f"Tenant DB replication warning: {te}\n{traceback.format_exc()}")
        
        return db_user
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Change user password"""
    
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(password_data.new_password)
    from datetime import datetime
    current_user.password_changed_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Password changed successfully"}


@router.get("/me")
async def read_users_me(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get current user with organization info"""
    # Get organization info if user belongs to one
    if current_user.organization_id:
        org_query = select(Organization).where(Organization.id == current_user.organization_id)
        org_result = await db.execute(org_query)
        organization = org_result.scalar_one_or_none()
        
        if organization:
            # Add organization info to user response
            user_dict = {
                "id": current_user.id,
                "email": current_user.email,
                "username": current_user.username,
                "first_name": current_user.first_name,
                "last_name": current_user.last_name,
                "phone": current_user.phone,
                "bio": current_user.bio,
                "timezone": current_user.timezone,
                "avatar_url": current_user.avatar_url,
                "organization_id": current_user.organization_id,
                "role": current_user.role,
                "status": current_user.status,
                "is_active": current_user.is_active,
                "is_verified": current_user.is_verified,
                "created_at": current_user.created_at,
                "updated_at": current_user.updated_at,
                "last_login": current_user.last_login,
                "preferences": current_user.preferences,
                "notification_settings": current_user.notification_settings,
                "organization": {
                    "id": organization.id,
                    "name": organization.name,
                    "slug": organization.slug
                }
            }
            return user_dict
    
    # If no organization, return basic user dict
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "phone": current_user.phone,
        "bio": current_user.bio,
        "timezone": current_user.timezone,
        "avatar_url": current_user.avatar_url,
        "organization_id": current_user.organization_id,
        "role": current_user.role,
        "status": current_user.status,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "last_login": current_user.last_login,
        "preferences": current_user.preferences,
        "notification_settings": current_user.notification_settings,
        "organization": None
    }


@router.post("/logout")
async def logout() -> Any:
    """Logout user (client should remove tokens)"""
    return {"message": "Successfully logged out"}
