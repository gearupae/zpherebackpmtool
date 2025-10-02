#!/usr/bin/env python3
"""Create test data for ZSphere development"""

import asyncio
import sys
import os
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.db.database import AsyncSessionLocal, engine
from app.models.user import User
from app.models.organization import Organization
from app.models.base import Base
from app.core.security import get_password_hash

async def create_test_data():
    """Create test user and organization for development"""
    
    # First create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created")
    
    async with AsyncSessionLocal() as db:
        try:
            # Check if test org already exists
            from sqlalchemy import select
            org_result = await db.execute(select(Organization).where(Organization.slug == "gear"))
            existing_org = org_result.scalar_one_or_none()
            
            if not existing_org:
                # Create test organization
                org = Organization(
                    id="ad0f185b-2768-4ba3-9321-a8a3591f080c",
                    name="Gear Company",
                    slug="gear", 
                    is_active=True,
                    subscription_tier="professional"
                )
                db.add(org)
                await db.flush()
                print("✅ Created test organization: Gear Company")
            else:
                print("✅ Test organization already exists")
                org = existing_org

            # Check if test user already exists
            user_result = await db.execute(select(User).where(User.email == "admin@gear.com"))
            existing_user = user_result.scalar_one_or_none()
            
            if not existing_user:
                # Create test user
                user = User(
                    id="test-user-id",
                    email="admin@gear.com",
                    username="admin",
                    first_name="Admin",
                    last_name="User",
                    hashed_password=get_password_hash("password"),
                    organization_id=org.id,
                    is_active=True,
                    is_verified=True,
                    status="ACTIVE",
                    role="ADMIN"
                )
                db.add(user)
                print("✅ Created test user: admin@gear.com / password")
            else:
                print("✅ Test user already exists")
            
            await db.commit()
            print("\n🎉 Test data ready!")
            print("📧 Email: admin@gear.com")
            print("🔑 Password: password")
            print("🏢 Organization: gear")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Error creating test data: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(create_test_data())
