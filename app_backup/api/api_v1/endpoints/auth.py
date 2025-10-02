from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ....db.database import get_db
from ....core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    verify_refresh_token,
    get_password_hash
)
from ....core.config import settings
from ....models.user import User
from ....models.organization import Organization
from ....schemas.auth import Token, LoginRequest, RefreshTokenRequest, ChangePasswordRequest
from ....schemas.user import UserCreate, UserRegister, User as UserSchema
import uuid
from ...deps import get_current_active_user

router = APIRouter()


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
            role="admin",  # First user is admin of their organization
            is_active=True,
            is_verified=False,
            status="active"
        )
        
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        
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


@router.get("/me", response_model=UserSchema)
async def read_users_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get current user"""
    return current_user


@router.post("/logout")
async def logout() -> Any:
    """Logout user (client should remove tokens)"""
    return {"message": "Successfully logged out"}
