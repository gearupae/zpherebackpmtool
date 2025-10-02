#!/usr/bin/env python3
"""
Complete Multi-Tenant System Setup
This script sets up the entire multi-tenant system with proper databases
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
import uuid

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

async def setup_complete_system():
    """Set up the complete multi-tenant system"""
    try:
        print("🚀 Setting up Complete Multi-Tenant System")
        print("=" * 60)
        
        # Import required modules
        from app.db.database import AsyncSessionLocal, init_db, engine
        from app.db.tenant_manager import tenant_manager, TenantBase
        from app.models.organization import Organization
        from app.models.user import User
        from app.models.tenant.customer import Customer as TenantCustomer
        from app.core.security import get_password_hash
        from sqlalchemy import select, text
        
        # Step 1: Initialize master database
        print("\n📦 Step 1: Initializing Master Database...")
        await init_db()
        print("✅ Master database initialized")
        
        # Step 2: Create organizations
        print("\n🏢 Step 2: Creating Organizations...")
        
        organizations_data = [
            {
                "name": "TechCorp Solutions",
                "slug": "techcorp",
                "description": "Leading technology solutions provider",
                "domain": "techcorp.com",
                "subscription_tier": "enterprise",
                "max_users": 100,
                "max_projects": 50
            },
            {
                "name": "DigitalWave Agency",
                "slug": "digitalwave", 
                "description": "Creative digital marketing agency",
                "domain": "digitalwave.io",
                "subscription_tier": "professional",
                "max_users": 25,
                "max_projects": 20
            },
            {
                "name": "InnovateLab",
                "slug": "innovatelab",
                "description": "Innovation and research laboratory",
                "domain": "innovatelab.com",
                "subscription_tier": "startup",
                "max_users": 10,
                "max_projects": 5
            }
        ]
        
        created_orgs = []
        
        async with AsyncSessionLocal() as session:
            for org_data in organizations_data:
                # Check if organization already exists
                result = await session.execute(
                    select(Organization).where(Organization.slug == org_data["slug"])
                )
                existing_org = result.scalar_one_or_none()
                
                if existing_org:
                    print(f"   📝 Organization {org_data['name']} already exists")
                    created_orgs.append(existing_org)
                else:
                    # Create new organization
                    org = Organization(
                        id=str(uuid.uuid4()),
                        name=org_data["name"],
                        slug=org_data["slug"],
                        description=org_data["description"],
                        domain=org_data["domain"],
                        is_active=True,
                        subscription_tier=org_data["subscription_tier"],
                        max_users=org_data["max_users"],
                        max_projects=org_data["max_projects"],
                        settings={}
                    )
                    session.add(org)
                    await session.commit()
                    await session.refresh(org)
                    created_orgs.append(org)
                    print(f"   ✅ Created organization: {org.name} (ID: {org.id})")
        
        # Step 3: Create users for each organization
        print("\n👥 Step 3: Creating Users...")
        
        users_data = [
            # TechCorp users
            {
                "username": "admin_techcorp",
                "email": "admin@techcorp.com",
                "password": "admin123",
                "first_name": "Tech",
                "last_name": "Admin",
                "role": "ADMIN",
                "org_slug": "techcorp"
            },
            {
                "username": "manager_techcorp",
                "email": "manager@techcorp.com", 
                "password": "manager123",
                "first_name": "Tech",
                "last_name": "Manager",
                "role": "MANAGER",
                "org_slug": "techcorp"
            },
            # DigitalWave users
            {
                "username": "admin_digitalwave",
                "email": "admin@digitalwave.io",
                "password": "admin123",
                "first_name": "Digital",
                "last_name": "Admin",
                "role": "ADMIN",
                "org_slug": "digitalwave"
            },
            {
                "username": "designer_digitalwave",
                "email": "designer@digitalwave.io",
                "password": "designer123",
                "first_name": "Creative",
                "last_name": "Designer",
                "role": "MEMBER",
                "org_slug": "digitalwave"
            },
            # InnovateLab users
            {
                "username": "admin_innovatelab",
                "email": "admin@innovatelab.com",
                "password": "admin123", 
                "first_name": "Innovation",
                "last_name": "Admin",
                "role": "ADMIN",
                "org_slug": "innovatelab"
            }
        ]
        
        async with AsyncSessionLocal() as session:
            for user_data in users_data:
                # Find the organization
                org = next((o for o in created_orgs if o.slug == user_data["org_slug"]), None)
                if not org:
                    continue
                
                # Check if user already exists
                result = await session.execute(
                    select(User).where(User.username == user_data["username"])
                )
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    print(f"   📝 User {user_data['username']} already exists")
                else:
                    # Create new user
                    user = User(
                        id=str(uuid.uuid4()),
                        username=user_data["username"],
                        email=user_data["email"],
                        first_name=user_data["first_name"],
                        last_name=user_data["last_name"],
                        hashed_password=get_password_hash(user_data["password"]),
                        is_active=True,
                        is_verified=True,
                        organization_id=org.id,
                        role=user_data["role"],
                        preferences={},
                        notification_settings={}
                    )
                    session.add(user)
                    await session.commit()
                    print(f"   ✅ Created user: {user.username} for {org.name}")
        
        # Step 4: Create tenant databases
        print("\n🗄️  Step 4: Creating Tenant Databases...")
        
        for org in created_orgs:
            print(f"\n   Creating tenant database for {org.name}...")
            
            # Create tenant database
            tenant_db_name = f"zphere_tenant_{org.id.replace('-', '_')}"
            
            try:
                # Check if database already exists
                async with engine.begin() as conn:
                    result = await conn.execute(
                        text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                        {"db_name": tenant_db_name}
                    )
                    db_exists = result.fetchone() is not None
                
                if not db_exists:
                    # Create the database
                    async with engine.begin() as conn:
                        await conn.execute(text(f'CREATE DATABASE "{tenant_db_name}"'))
                    print(f"     ✅ Created database: {tenant_db_name}")
                else:
                    print(f"     📝 Database {tenant_db_name} already exists")
                
                # Initialize tenant database schema
                tenant_engine = await tenant_manager.get_tenant_engine(org.id)
                
                # Create all tenant tables
                async with tenant_engine.begin() as conn:
                    await conn.run_sync(TenantBase.metadata.create_all)
                
                print(f"     ✅ Initialized schema for {org.name}")
                
                # Add sample customer data
                from sqlalchemy.ext.asyncio import async_sessionmaker
                TenantSessionLocal = async_sessionmaker(
                    tenant_engine, expire_on_commit=False
                )
                
                # Sample customers for each tenant
                customers_data = [
                    {
                        "first_name": "John",
                        "last_name": "Smith",
                        "email": f"john.smith@{org.domain}",
                        "phone": "+1-555-0101",
                        "company_name": f"{org.name} Client Corp",
                        "company_website": f"https://{org.slug}client.com",
                        "job_title": "CEO",
                        "address_line_1": "123 Business Ave",
                        "city": "New York",
                        "state": "NY",
                        "postal_code": "10001",
                        "country": "USA",
                        "customer_type": "client",
                        "credit_limit": 50000,
                        "payment_terms": "net_30"
                    },
                    {
                        "first_name": "Sarah",
                        "last_name": "Johnson",
                        "email": f"sarah.johnson@{org.domain.replace('.', '')}.prospect.com",
                        "phone": "+1-555-0102",
                        "company_name": f"{org.name} Prospect Inc",
                        "job_title": "CTO",
                        "address_line_1": "456 Tech Street",
                        "city": "San Francisco",
                        "state": "CA", 
                        "postal_code": "94102",
                        "country": "USA",
                        "customer_type": "prospect",
                        "credit_limit": 25000,
                        "payment_terms": "net_15"
                    },
                    {
                        "first_name": "Michael",
                        "last_name": "Brown",
                        "email": f"michael.brown@{org.slug}enterprise.com",
                        "phone": "+1-555-0103",
                        "company_name": f"{org.name} Enterprise Solutions",
                        "job_title": "VP Operations",
                        "address_line_1": "789 Corporate Blvd",
                        "city": "Chicago",
                        "state": "IL",
                        "postal_code": "60601",
                        "country": "USA",
                        "customer_type": "client",
                        "credit_limit": 100000,
                        "payment_terms": "net_45"
                    }
                ]
                
                async with TenantSessionLocal() as tenant_session:
                    for customer_data in customers_data:
                        # Check if customer already exists
                        result = await tenant_session.execute(
                            select(TenantCustomer).where(TenantCustomer.email == customer_data["email"])
                        )
                        existing_customer = result.scalar_one_or_none()
                        
                        if not existing_customer:
                            customer = TenantCustomer(
                                id=str(uuid.uuid4()),
                                **customer_data,
                                is_active=True,
                                tags=[],
                                custom_fields={}
                            )
                            tenant_session.add(customer)
                    
                    await tenant_session.commit()
                    print(f"     ✅ Added sample customers for {org.name}")
                
                # Update organization settings
                async with AsyncSessionLocal() as session:
                    org_to_update = await session.get(Organization, org.id)
                    if org_to_update:
                        org_to_update.settings = {
                            "database_created": True,
                            "database_name": tenant_db_name
                        }
                        await session.commit()
                        print(f"     ✅ Updated organization settings for {org.name}")
                
            except Exception as e:
                print(f"     ❌ Error creating tenant database for {org.name}: {e}")
                continue
        
        # Step 5: Display credentials
        print("\n🔑 Step 5: System Credentials")
        print("=" * 60)
        
        print("\n📋 TENANT CREDENTIALS:")
        print("-" * 40)
        
        for org in created_orgs:
            print(f"\n🏢 {org.name} ({org.slug})")
            print(f"   Tenant ID: {org.id}")
            print(f"   Tenant Slug: {org.slug}")
            print(f"   Domain: {org.domain}")
            
            # Get users for this org
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(User).where(User.organization_id == org.id)
                )
                org_users = result.scalars().all()
                
                print("   👥 Users:")
                for user in org_users:
                    password = "admin123" if user.role == "ADMIN" else f"{user.role.lower()}123"
                    print(f"      • {user.username} ({user.role})")
                    print(f"        Email: {user.email}")
                    print(f"        Password: {password}")
        
        print("\n🌐 API ENDPOINTS:")
        print("-" * 40)
        print("Backend: http://localhost:8000")
        print("Frontend: http://localhost:3000")
        print("\nAPI Documentation: http://localhost:8000/docs")
        
        print("\n📱 FRONTEND ACCESS:")
        print("-" * 40)
        print("1. Open http://localhost:3000")
        print("2. Login with any of the credentials above")
        print("3. The system will automatically detect the tenant")
        
        print("\n✅ Complete Multi-Tenant System Setup Finished!")
        print("🎉 You can now test the full system with real data!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up system: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(setup_complete_system())
