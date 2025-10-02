#!/usr/bin/env python3
"""
Create a tenant with its own database
"""
import asyncio
import sys
import os
import uuid
from passlib.context import CryptContext

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_tenant_with_db():
    """Create a tenant with its own database"""
    print("🏢 Creating Tenant with Dedicated Database")
    print("=" * 50)
    
    try:
        from app.db.tenant_manager import tenant_manager
        from app.db.database import engine, AsyncSessionLocal
        from app.models.organization import Organization
        from app.models.user import User, UserRole, UserStatus
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # 1. Create organization in master database
        print("\n1. Creating organization in master database...")
        
        tenant_id = str(uuid.uuid4())
        tenant_slug = "motormindee"  # This will be used for tenant identification
        tenant_name = "MotorMindee"
        
        # Get master session
        master_session = await tenant_manager.get_master_session()
        
        try:
            # Check if organization already exists
            result = await master_session.execute(
                select(Organization).where(Organization.slug == tenant_slug)
            )
            existing_org = result.scalar_one_or_none()
            
            if existing_org:
                print(f"   ⚠️  Organization {tenant_slug} already exists, using existing one")
                org = existing_org
                tenant_id = org.id
            else:
                # Create new organization
                org = Organization(
                    id=tenant_id,
                    name=tenant_name,
                    slug=tenant_slug,
                    description="A test tenant organization with its own database",
                    domain=f"{tenant_slug}.com",
                    is_active=True,
                    subscription_tier="professional",
                    max_users=25,
                    max_projects=100,
                    # Store database info in settings
                    settings={
                        "database_created": False,
                        "database_name": f"zphere_tenant_{tenant_id}"
                    }
                )
                master_session.add(org)
                await master_session.flush()
                print(f"   ✅ Organization created: {org.name}")
            
            # Create tenant admin user
            result = await master_session.execute(
                select(User).where(User.email == f"tenant@{tenant_slug}.com")
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print(f"   ⚠️  Tenant admin already exists, using existing one")
                tenant_admin = existing_user
            else:
                # Create tenant admin user
                hashed_password = pwd_context.hash("tenant123")
                tenant_admin = User(
                    id=str(uuid.uuid4()),
                    email=f"tenant@{tenant_slug}.com",
                    username=f"{tenant_slug}_admin",
                    first_name="Tenant",
                    last_name="Admin",
                    hashed_password=hashed_password,
                    organization_id=tenant_id,
                    role=UserRole.ADMIN,
                    is_active=True,
                    is_verified=True,
                    status=UserStatus.ACTIVE
                )
                master_session.add(tenant_admin)
                print(f"   ✅ Tenant admin created: {tenant_admin.email}")
            
            # Create tenant user
            result = await master_session.execute(
                select(User).where(User.email == f"user@{tenant_slug}.com")
            )
            existing_tenant_user = result.scalar_one_or_none()
            
            if not existing_tenant_user:
                hashed_password = pwd_context.hash("user123")
                tenant_user = User(
                    id=str(uuid.uuid4()),
                    email=f"user@{tenant_slug}.com",
                    username=f"{tenant_slug}_user",
                    first_name="Regular",
                    last_name="User",
                    hashed_password=hashed_password,
                    organization_id=tenant_id,
                    role=UserRole.MEMBER,
                    is_active=True,
                    is_verified=True,
                    status=UserStatus.ACTIVE
                )
                master_session.add(tenant_user)
                print(f"   ✅ Tenant user created: {tenant_user.email}")
            
            await master_session.commit()
            
        except Exception as e:
            await master_session.rollback()
            print(f"   ❌ Error creating organization: {e}")
            raise
        finally:
            await master_session.close()
        
        # 2. Create tenant database
        print("\n2. Creating tenant database...")
        
        # Check if database is already created
        db_created = org.settings.get("database_created", False) if org.settings else False
        
        if not db_created:
            success = await tenant_manager.create_tenant_database(tenant_id)
            if success:
                print(f"   ✅ Tenant database created: zphere_tenant_{tenant_id}")
                
                # Update organization settings
                master_session = await tenant_manager.get_master_session()
                try:
                    result = await master_session.execute(
                        select(Organization).where(Organization.id == tenant_id)
                    )
                    org = result.scalar_one_or_none()
                    if org:
                        if not org.settings:
                            org.settings = {}
                        org.settings["database_created"] = True
                        org.settings["database_name"] = f"zphere_tenant_{tenant_id}"
                        await master_session.commit()
                except Exception as e:
                    await master_session.rollback()
                    print(f"   ⚠️  Error updating organization: {e}")
                finally:
                    await master_session.close()
            else:
                print("   ❌ Failed to create tenant database")
                return False
        else:
            print("   ✅ Tenant database already exists")
        
        # 3. Add sample data to tenant database
        print("\n3. Adding sample data to tenant database...")
        
        tenant_session = await tenant_manager.get_tenant_session(tenant_id)
        
        try:
            # Import tenant-specific models
            from app.models.tenant.customer import Customer
            
            # Create sample customer
            customer = Customer(
                id=str(uuid.uuid4()),
                first_name="John",
                last_name="Smith",
                email="john.smith@example.com",
                company_name="Example Corp",
                job_title="CEO",
                phone="+1-555-0123",
                is_active=True,
                customer_type="client"
            )
            
            tenant_session.add(customer)
            await tenant_session.flush()
            print(f"   ✅ Sample customer created: {customer.first_name} {customer.last_name}")
            
            await tenant_session.commit()
            
        except Exception as e:
            await tenant_session.rollback()
            print(f"   ❌ Error creating sample data: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await tenant_session.close()
        
        # Display credentials
        print("\n" + "=" * 60)
        print("🎉 TENANT CREATED SUCCESSFULLY!")
        print("=" * 60)
        
        print(f"\n🏢 ORGANIZATION DETAILS:")
        print(f"   Name: {tenant_name}")
        print(f"   Slug: {tenant_slug}")
        print(f"   ID: {tenant_id}")
        print(f"   Database: zphere_tenant_{tenant_id}")
        
        print(f"\n👤 USER CREDENTIALS:")
        print(f"   📧 Tenant Admin:")
        print(f"      Email: tenant@{tenant_slug}.com")
        print(f"      Password: tenant123")
        
        print(f"\n   📧 Regular User:")
        print(f"      Email: user@{tenant_slug}.com")
        print(f"      Password: user123")
        
        print(f"\n🌐 API ENDPOINTS:")
        print(f"   Base URL: http://localhost:8000/api/v1")
        print(f"   Login: POST /auth/login")
        print(f"   Docs: http://localhost:8000/api/v1/docs")
        
        print(f"\n📋 TENANT HEADERS FOR API REQUESTS:")
        print(f'   X-Tenant-Type: "tenant"')
        print(f'   X-Tenant-Slug: "{tenant_slug}"')
        print(f'   X-Tenant-Id: "{tenant_id}"')
        
        print(f"\n🔧 TESTING THE SETUP:")
        print(f"   1. Start the backend: python run.py")
        print(f"   2. Start the frontend: cd ../frontend && npm start")
        print(f"   3. Login with tenant@{tenant_slug}.com / tenant123")
        
        print("\n" + "=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to create tenant: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Don't close connections - leave them for the running app
        pass


if __name__ == "__main__":
    success = asyncio.run(create_tenant_with_db())
    sys.exit(0 if success else 1)