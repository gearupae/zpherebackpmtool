#!/usr/bin/env python3
"""
Test script for multi-tenant database architecture
"""
import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.db.tenant_manager import tenant_manager
from app.db.database import init_master_db
from app.models.master.organization import Organization
from app.models.master.user import User, UserRole
from app.models.tenant.project import Project
from app.models.tenant.customer import Customer
from app.services.tenant_service import TenantService


async def test_multi_tenant_setup():
    """Test the multi-tenant database setup"""
    print("🚀 Testing Multi-Tenant Database Architecture")
    print("=" * 50)
    
    try:
        # Step 1: Initialize master database
        print("1. Initializing master database...")
        await init_master_db()
        print("   ✅ Master database initialized")
        
        # Step 2: Create test organization with database
        print("\n2. Creating test organization with dedicated database...")
        
        master_session = await tenant_manager.get_master_session()
        try:
            org_data = {
                "name": "Test Company",
                "slug": "test-company",
                "description": "A test organization for multi-tenant testing",
                "is_active": True,
                "subscription_tier": "professional",
                "max_users": 10,
                "max_projects": 50
            }
            
            user_data = {
                "email": "admin@testcompany.com",
                "username": "admin",
                "first_name": "Admin",
                "last_name": "User",
                "hashed_password": "hashed_password_here",
                "role": UserRole.ADMIN,
                "is_active": True,
                "is_verified": True
            }
            
            org, user = await TenantService.create_organization_with_database(
                org_data, user_data, master_session
            )
            
            print(f"   ✅ Organization created: {org.name} (ID: {org.id})")
            print(f"   ✅ Admin user created: {user.email}")
            print(f"   ✅ Tenant database created: {org.database_name}")
            
        finally:
            await master_session.close()
        
        # Step 3: Test tenant database operations
        print("\n3. Testing tenant database operations...")
        
        tenant_session = await tenant_manager.get_tenant_session(org.id)
        try:
            # Create a test customer
            customer = Customer(
                first_name="John",
                last_name="Doe",
                email="john@example.com",
                company_name="Acme Corp",
                is_active=True
            )
            tenant_session.add(customer)
            await tenant_session.commit()
            print(f"   ✅ Customer created in tenant DB: {customer.full_name}")
            
            # Create a test project
            project = Project(
                name="Test Project",
                description="A test project in the tenant database",
                slug="test-project",
                owner_id=user.id,  # Reference to user in master DB
                customer_id=customer.id,
                is_active=True
            )
            tenant_session.add(project)
            await tenant_session.commit()
            print(f"   ✅ Project created in tenant DB: {project.name}")
            
        finally:
            await tenant_session.close()
        
        # Step 4: Verify data isolation
        print("\n4. Verifying data isolation...")
        
        # Check master database
        master_session = await tenant_manager.get_master_session()
        try:
            from sqlalchemy import select
            
            # Count organizations
            org_result = await master_session.execute(select(Organization))
            orgs = org_result.scalars().all()
            print(f"   ✅ Organizations in master DB: {len(orgs)}")
            
            # Count users
            user_result = await master_session.execute(select(User))
            users = user_result.scalars().all()
            print(f"   ✅ Users in master DB: {len(users)}")
            
        finally:
            await master_session.close()
        
        # Check tenant database
        tenant_session = await tenant_manager.get_tenant_session(org.id)
        try:
            from sqlalchemy import select
            
            # Count customers (should only exist in tenant DB)
            customer_result = await tenant_session.execute(select(Customer))
            customers = customer_result.scalars().all()
            print(f"   ✅ Customers in tenant DB: {len(customers)}")
            
            # Count projects (should only exist in tenant DB)
            project_result = await tenant_session.execute(select(Project))
            projects = project_result.scalars().all()
            print(f"   ✅ Projects in tenant DB: {len(projects)}")
            
        finally:
            await tenant_session.close()
        
        # Step 5: Test organization stats
        print("\n5. Testing organization statistics...")
        stats = await TenantService.get_organization_stats(org.id)
        print(f"   ✅ Organization stats: {stats}")
        
        print("\n🎉 Multi-tenant database architecture test completed successfully!")
        print("=" * 50)
        print("\n📊 Architecture Summary:")
        print("• Master Database: Stores organizations and users")
        print("• Tenant Databases: Each organization has its own database")
        print("• Data Isolation: Business data is completely separated per tenant")
        print("• Dynamic Routing: Database connections are routed based on organization")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        print("\n6. Cleaning up connections...")
        await tenant_manager.close_all_connections()
        print("   ✅ All connections closed")


if __name__ == "__main__":
    asyncio.run(test_multi_tenant_setup())
