#!/usr/bin/env python3
"""
Create tenant database for motormindee organization
"""
import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

async def fix_motormindee_tenant():
    """Create tenant database for motormindee organization"""
    print("🏢 Creating Motormindee Tenant Database")
    print("=" * 50)
    
    try:
        from app.db.tenant_manager import TenantDatabaseManager, TenantBase
        
        # Initialize tenant manager
        tenant_manager = TenantDatabaseManager()
        
        # The motormindee organization ID from the logs
        org_id = "2b1a0f81-803e-46af-b167-2012e3420def"
        
        print(f"Creating tenant database for Motormindee: {org_id}")
        
        # Create tenant database
        print("1. Creating tenant database...")
        success = await tenant_manager.create_tenant_database(org_id)
        
        if success:
            print(f"✅ Tenant database created: zphere_tenant_{org_id}")
        else:
            print("❌ Failed to create tenant database")
            return False
        
        # Import all tenant models to register them with TenantBase
        print("2. Importing tenant models...")
        from app.models.tenant.customer import Customer
        
        print(f"Registered tenant models: {list(TenantBase.metadata.tables.keys())}")
        
        # Get tenant engine and create schema
        print("3. Creating database schema...")
        engine = tenant_manager._get_tenant_engine(org_id)
        
        # Create all tables in the tenant database
        async with engine.begin() as conn:
            await conn.run_sync(TenantBase.metadata.create_all)
        
        print("✅ Tenant database schema created!")
        
        # Test tenant database connection
        try:
            tenant_session = await tenant_manager.get_tenant_session(org_id)
            
            # Test a simple query to verify table exists
            from sqlalchemy import text
            result = await tenant_session.execute(text("SELECT COUNT(*) FROM tenant_customers"))
            count = result.scalar()
            print(f"✅ Database verification successful! Found {count} customers.")
            
            await tenant_session.close()
            
        except Exception as e:
            print(f"⚠️  Database created but verification failed: {e}")
        
        print("\n🎉 Motormindee tenant database setup complete!")
        print("You should now be able to create customers and other resources!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating motormindee tenant: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(fix_motormindee_tenant())
    sys.exit(0 if success else 1)
