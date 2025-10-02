#!/usr/bin/env python3
"""
Create demo users based on the login guide
"""
import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from passlib.context import CryptContext

# Database URL
DATABASE_URL = "sqlite+aiosqlite:///./zphere.db"

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_demo_users():
    print("🚀 Creating Demo Users...")
    
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    # Create session factory
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            # Import models here to avoid circular imports
            from app.models.user import User, UserRole, UserStatus
            from app.models.organization import Organization
            
            # Check/Create organization first
            org_result = await session.execute(select(Organization).where(Organization.slug == "demo-org"))
            organization = org_result.scalar_one_or_none()
            
            if not organization:
                print("📋 Creating demo organization...")
                organization = Organization(
                    id=str(uuid.uuid4()),
                    name="Demo Organization",
                    slug="demo-org",
                    description="Demo organization for testing",
                    domain="demo.com",
                    is_active=True,
                    subscription_tier="premium",
                    max_users=50,
                    max_projects=100
                )
                session.add(organization)
                await session.flush()
                print(f"✅ Organization created: {organization.name}")
            else:
                print(f"✅ Using existing organization: {organization.name}")
            
            # Create admin user
            admin_result = await session.execute(
                select(User).where(User.email == "admin@zphere.com")
            )
            admin_user = admin_result.scalar_one_or_none()
            
            if not admin_user:
                print("👑 Creating admin user...")
                admin_user = User(
                    id=str(uuid.uuid4()),
                    email="admin@zphere.com",
                    username="admin",
                    first_name="Admin",
                    last_name="User",
                    hashed_password=pwd_context.hash("admin123"),
                    organization_id=organization.id,
                    role=UserRole.ADMIN,
                    status=UserStatus.ACTIVE,
                    is_active=True,
                    is_verified=True,
                    timezone="UTC"
                )
                session.add(admin_user)
                print("✅ Admin user created")
            else:
                print("✅ Admin user already exists")
            
            # Create tenant user
            tenant_result = await session.execute(
                select(User).where(User.email == "tenant@demo.com")
            )
            tenant_user = tenant_result.scalar_one_or_none()
            
            if not tenant_user:
                print("👤 Creating tenant user...")
                tenant_user = User(
                    id=str(uuid.uuid4()),
                    email="tenant@demo.com",
                    username="tenant",
                    first_name="Tenant",
                    last_name="User",
                    hashed_password=pwd_context.hash("tenant123"),
                    organization_id=organization.id,
                    role=UserRole.TENANT,
                    status=UserStatus.ACTIVE,
                    is_active=True,
                    is_verified=True,
                    timezone="UTC"
                )
                session.add(tenant_user)
                print("✅ Tenant user created")
            else:
                print("✅ Tenant user already exists")
            
            await session.commit()
            
            print("\n" + "=" * 60)
            print("🎉 DEMO USERS CREATED SUCCESSFULLY!")
            print("=" * 60)
            
            print("\n🛡️ ADMIN LOGIN:")
            print("   Email: admin@zphere.com")
            print("   Password: admin123")
            print("   Role: ADMIN")
            
            print("\n👤 TENANT LOGIN:")
            print("   Email: tenant@demo.com")
            print("   Password: tenant123")
            print("   Role: TENANT")
            
            print("\n🌐 FRONTEND URL:")
            print("   http://localhost:3000/login")
            
            print("\n🔧 BACKEND API:")
            print("   http://localhost:8000/api/v1/docs")
            
            print("\n" + "=" * 60)
            
        except Exception as e:
            print(f"❌ Error creating demo users: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_demo_users())
