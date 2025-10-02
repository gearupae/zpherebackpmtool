#!/usr/bin/env python3
"""
Script to create a test user for development
"""
import asyncio
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.security import get_password_hash
from app.models.user import User, UserRole, UserStatus
from app.models.organization import Organization

# Database URL
DATABASE_URL = "sqlite+aiosqlite:///./zphere.db"

async def create_test_user():
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    # Create session factory
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            # Check if test user already exists
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.email == "admin@zphere.com")
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print("Test user already exists!")
                return
            
            # Get the first organization
            org_result = await session.execute(select(Organization))
            organization = org_result.scalar_one_or_none()
            
            if not organization:
                print("No organization found! Please create an organization first.")
                return
            
            # Create test user
            test_user = User(
                id=str(uuid.uuid4()),
                email="admin@zphere.com",
                username="admin",
                first_name="Admin",
                last_name="User",
                hashed_password=get_password_hash("admin123"),
                organization_id=organization.id,
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                is_active=True,
                is_verified=True,
                timezone="UTC",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            session.add(test_user)
            await session.commit()
            
            print("✅ Test user created successfully!")
            print("📧 Email: admin@zphere.com")
            print("👤 Username: admin")
            print("🔑 Password: admin123")
            print("🏢 Organization: " + organization.name)
            
        except Exception as e:
            print(f"❌ Error creating test user: {e}")
            await session.rollback()
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_test_user())
