#!/usr/bin/env python3
"""
Create a test tenant organization with user credentials
"""
import asyncio
import sys
import os
import uuid
from passlib.context import CryptContext

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_test_tenant():
    """Create a test tenant with credentials"""
    print("🏢 Creating Test Tenant Organization")
    print("=" * 50)
    
    try:
        from app.db.tenant_manager import tenant_manager
        from app.db.database import init_master_db
        from app.models.master.organization import Organization
        from app.models.master.user import User, UserRole, UserStatus
        from app.models.tenant.project import Project
        from app.models.tenant.customer import Customer
        from sqlalchemy import select
        
        # Initialize master database
        print("1. Initializing master database...")
        await init_master_db()
        print("   ✅ Master database initialized")
        
        # Create test organization
        print("\n2. Creating test organization...")
        
        master_session = await tenant_manager.get_master_session()
        try:
            # Check if organization already exists
            result = await master_session.execute(
                select(Organization).where(Organization.slug == "test-company")
            )
            existing_org = result.scalar_one_or_none()
            
            if existing_org:
                print("   ⚠️  Test organization already exists, using existing one")
                org = existing_org
            else:
                # Create new organization
                org = Organization(
                    id=str(uuid.uuid4()),
                    name="Test Company Ltd",
                    slug="test-company",
                    description="A test organization for development and testing",
                    domain="testcompany.com",
                    is_active=True,
                    subscription_tier="professional",
                    max_users=25,
                    max_projects=100,
                    database_created=False
                )
                master_session.add(org)
                await master_session.flush()
                print(f"   ✅ Organization created: {org.name}")
            
            # Check if admin user already exists
            result = await master_session.execute(
                select(User).where(User.email == "admin@testcompany.com")
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print("   ⚠️  Admin user already exists, using existing one")
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
                master_session.add(admin_user)
                print(f"   ✅ Admin user created: {admin_user.email}")
            
            # Create manager user
            result = await master_session.execute(
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
                    role=UserRole.TENANT,
                    is_active=True,
                    is_verified=True,
                    status=UserStatus.ACTIVE
                )
                master_session.add(manager_user)
                print(f"   ✅ Manager user created: {manager_user.email}")
            
            await master_session.commit()
            
        finally:
            await master_session.close()
        
        # Create tenant database
        print("\n3. Creating tenant database...")
        if not org.database_created:
            success = await tenant_manager.create_tenant_database(org.id)
            if success:
                print(f"   ✅ Tenant database created: zphere_tenant_{org.id}")
                
                # Update organization
                master_session = await tenant_manager.get_master_session()
                try:
                    org.database_created = True
                    org.database_name = f"zphere_tenant_{org.id}"
                    master_session.add(org)
                    await master_session.commit()
                finally:
                    await master_session.close()
            else:
                print("   ❌ Failed to create tenant database")
                return False
        else:
            print("   ✅ Tenant database already exists")
        
        # Add sample data to tenant database
        print("\n4. Adding sample data to tenant database...")
        
        tenant_session = await tenant_manager.get_tenant_session(org.id)
        try:
            # Check if sample data already exists
            from sqlalchemy import select
            result = await tenant_session.execute(select(Customer))
            existing_customers = result.scalars().all()
            
            if not existing_customers:
                # Create sample customers
                customer1 = Customer(
                    id=str(uuid.uuid4()),
                    first_name="John",
                    last_name="Smith",
                    email="john.smith@clientcorp.com",
                    company_name="Client Corporation",
                    job_title="CEO",
                    phone="+1-555-0123",
                    is_active=True,
                    customer_type="client"
                )
                
                customer2 = Customer(
                    id=str(uuid.uuid4()),
                    first_name="Sarah",
                    last_name="Johnson",
                    email="sarah@startupxyz.com",
                    company_name="Startup XYZ",
                    job_title="Founder",
                    phone="+1-555-0456",
                    is_active=True,
                    customer_type="prospect"
                )
                
                tenant_session.add(customer1)
                tenant_session.add(customer2)
                await tenant_session.flush()
                
                # Create sample projects
                project1 = Project(
                    id=str(uuid.uuid4()),
                    name="Website Redesign",
                    description="Complete redesign of company website with modern UI/UX",
                    slug="website-redesign",
                    owner_id=admin_user.id,
                    customer_id=customer1.id,
                    budget=50000,  # $500.00 in cents
                    estimated_hours=120
                )
                
                project2 = Project(
                    id=str(uuid.uuid4()),
                    name="Mobile App Development",
                    description="Develop cross-platform mobile application",
                    slug="mobile-app-dev",
                    owner_id=admin_user.id,
                    customer_id=customer2.id,
                    budget=100000,  # $1000.00 in cents
                    estimated_hours=200
                )
                
                tenant_session.add(project1)
                tenant_session.add(project2)
                
                await tenant_session.commit()
                print("   ✅ Sample customers and projects added")
            else:
                print("   ✅ Sample data already exists")
                
        finally:
            await tenant_session.close()
        
        # Display credentials
        print("\n" + "=" * 60)
        print("🎉 TEST TENANT CREATED SUCCESSFULLY!")
        print("=" * 60)
        
        print(f"\n🏢 ORGANIZATION DETAILS:")
        print(f"   Name: {org.name}")
        print(f"   Slug: {org.slug}")
        print(f"   ID: {org.id}")
        print(f"   Database: {org.database_name}")
        print(f"   Tier: {org.subscription_tier}")
        
        print(f"\n👤 USER CREDENTIALS:")
        print(f"   📧 Admin Login:")
        print(f"      Email: admin@testcompany.com")
        print(f"      Password: admin123")
        print(f"      Role: Admin")
        
        print(f"\n   📧 Manager Login:")
        print(f"      Email: manager@testcompany.com")
        print(f"      Password: manager123")
        print(f"      Role: Manager")
        
        print(f"\n🌐 API ENDPOINTS:")
        print(f"   Base URL: http://localhost:8000/api/v1")
        print(f"   Login: POST /auth/login")
        print(f"   Docs: http://localhost:8000/api/v1/docs")
        
        print(f"\n📋 SAMPLE DATA INCLUDED:")
        print(f"   • 2 Sample customers")
        print(f"   • 2 Sample projects")
        print(f"   • Complete tenant database setup")
        
        print(f"\n🔧 TESTING THE SETUP:")
        print(f"   1. Start the backend: python run.py")
        print(f"   2. Login with admin@testcompany.com / admin123")
        print(f"   3. Check API docs at http://localhost:8000/api/v1/docs")
        
        print("\n" + "=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to create test tenant: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Don't close connections - leave them for the running app
        pass


if __name__ == "__main__":
    success = asyncio.run(create_test_tenant())
    sys.exit(0 if success else 1)
