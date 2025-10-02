#!/usr/bin/env python3
"""
Create a demo tenant user with known credentials
"""
import asyncio
import sys
import os
sys.path.append('/Users/ajaskv/Project/zphere/backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.core.security import get_password_hash
from app.models.user import User, UserRole, UserStatus
from app.models.organization import Organization
from app.core.config import settings
import uuid

async def create_demo_tenant_user():
    """Create a demo tenant user"""
    
    # Create async engine using the actual database URL
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    
    # Create session factory
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Check if demo tenant organization exists
            org_result = await session.execute(
                select(Organization).where(Organization.id == "3b7dab97-32bc-41b6-85bc-2df9428e5238")
            )
            demo_org = org_result.scalar_one_or_none()
            
            if not demo_org:
                print("❌ Demo Tenant organization not found!")
                return
            
            print(f"✅ Found Demo Tenant Organization: {demo_org.name}")
            print(f"   Organization ID: {demo_org.id}")
            
            # Check if user already exists
            user_result = await session.execute(
                select(User).where(User.email == "testuser@demo-tenant.com")
            )
            existing_user = user_result.scalar_one_or_none()
            
            if existing_user:
                print("✅ Test user already exists!")
                print("📧 Email: testuser@demo-tenant.com")
                print("🔑 Password: testpass123")
                print("🏢 Organization: Demo Tenant Company")
                return
            
            # Create new test user
            new_user = User(
                id=str(uuid.uuid4()),
                email="testuser@demo-tenant.com",
                username="testuser",
                first_name="Test",
                last_name="User",
                hashed_password=get_password_hash("testpass123"),
                organization_id=demo_org.id,
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                is_active=True,
                is_verified=True,
                timezone="UTC"
            )
            
            session.add(new_user)
            await session.commit()
            
            print("✅ Demo tenant user created successfully!")
            print("📧 Email: testuser@demo-tenant.com")
            print("🔑 Password: testpass123")
            print("👤 Role: ADMIN")
            print("🏢 Organization: Demo Tenant Company")
            print(f"🗃️  Organization ID: {demo_org.id}")
            
            return {
                "email": "testuser@demo-tenant.com",
                "password": "testpass123",
                "organization": demo_org.name,
                "organization_id": demo_org.id
            }
            
        except Exception as e:
            print(f"❌ Error: {e}")
            await session.rollback()
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_demo_tenant_user())