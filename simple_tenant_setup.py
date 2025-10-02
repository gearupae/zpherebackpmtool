#!/usr/bin/env python3
"""
Simple tenant setup using existing backend structure
"""
import asyncio
import sys
import os
import uuid
from passlib.context import CryptContext

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_simple_tenant():
    """Create a tenant using existing models"""
    print("🏢 Creating Test Tenant (Simple Method)")
    print("=" * 50)
    
    try:
        from app.db.database import get_db, init_db
        from app.models.organization import Organization
        from app.models.user import User, UserRole, UserStatus
        from app.models.project import Project
        from app.models.customer import Customer
        from sqlalchemy import select
        
        # Initialize database
        print("1. Initializing database...")
        await init_db()
        print("   ✅ Database initialized")
        
        # Get database session
        async for session in get_db():
            try:
                # Check if test organization exists
                result = await session.execute(
                    select(Organization).where(Organization.slug == "test-company")
                )
                existing_org = result.scalar_one_or_none()
                
                if existing_org:
                    print("   ⚠️  Test organization already exists")
                    org = existing_org
                else:
                    # Create organization
                    org = Organization(
                        id=str(uuid.uuid4()),
                        name="Test Company Ltd",
                        slug="test-company",
                        description="A test organization for development",
                        is_active=True,
                        subscription_tier="professional"
                    )
                    session.add(org)
                    await session.flush()
                    print(f"   ✅ Organization created: {org.name}")
                
                # Check if admin user exists
                result = await session.execute(
                    select(User).where(User.email == "admin@testcompany.com")
                )
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    print("   ⚠️  Admin user already exists")
                    admin_user = existing_user
                else:
                    # Create admin user
                    hashed_password = pwd_context.hash("admin123")
                    admin_user = User(
                        id=str(uuid.uuid4()),
                        email="admin@testcompany.com",
                        username="admin",
                        first_name="Admin",
                        last_name="User",
                        hashed_password=hashed_password,
                        organization_id=org.id,
                        role=UserRole.ADMIN,
                        is_active=True,
                        is_verified=True,
                        status=UserStatus.ACTIVE
                    )
                    session.add(admin_user)
                    print(f"   ✅ Admin user created: {admin_user.email}")
                
                # Create manager user if not exists
                result = await session.execute(
                    select(User).where(User.email == "manager@testcompany.com")
                )
                existing_manager = result.scalar_one_or_none()
                
                if not existing_manager:
                    hashed_password = pwd_context.hash("manager123")
                    manager_user = User(
                        id=str(uuid.uuid4()),
                        email="manager@testcompany.com",
                        username="manager",
                        first_name="Project",
                        last_name="Manager",
                        hashed_password=hashed_password,
                        organization_id=org.id,
                        role=UserRole.MANAGER,
                        is_active=True,
                        is_verified=True,
                        status=UserStatus.ACTIVE
                    )
                    session.add(manager_user)
                    print(f"   ✅ Manager user created: {manager_user.email}")
                
                # Check for existing sample data
                result = await session.execute(
                    select(Customer).where(Customer.organization_id == org.id)
                )
                existing_customers = result.scalars().all()
                
                if not existing_customers:
                    # Create sample customer
                    customer = Customer(
                        id=str(uuid.uuid4()),
                        first_name="John",
                        last_name="Smith",
                        email="john.smith@clientcorp.com",
                        company_name="Client Corporation",
                        organization_id=org.id,
                        is_active=True
                    )
                    session.add(customer)
                    await session.flush()
                    
                    # Create sample project
                    project = Project(
                        id=str(uuid.uuid4()),
                        name="Website Redesign",
                        description="Complete website redesign project",
                        slug="website-redesign",
                        organization_id=org.id,
                        owner_id=admin_user.id,
                        customer_id=customer.id
                    )
                    session.add(project)
                    print("   ✅ Sample data created")
                
                await session.commit()
                
                # Display credentials
                print("\n" + "=" * 60)
                print("🎉 TEST TENANT READY!")
                print("=" * 60)
                
                print(f"\n🏢 ORGANIZATION:")
                print(f"   Name: {org.name}")
                print(f"   ID: {org.id}")
                
                print(f"\n👤 CREDENTIALS:")
                print(f"   📧 Admin:")
                print(f"      Email: admin@testcompany.com")
                print(f"      Password: admin123")
                
                print(f"\n   📧 Manager:")
                print(f"      Email: manager@testcompany.com")
                print(f"      Password: manager123")
                
                print(f"\n🌐 USAGE:")
                print(f"   1. Start backend: cd backend && python run.py")
                print(f"   2. API Docs: http://localhost:8000/api/v1/docs")
                print(f"   3. Login endpoint: POST /api/v1/auth/login")
                
                print("\n" + "=" * 60)
                
                return True
                
            except Exception as e:
                await session.rollback()
                raise e
            
            break  # Exit the async generator
        
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(create_simple_tenant())
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
