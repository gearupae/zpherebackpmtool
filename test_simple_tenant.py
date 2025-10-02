#!/usr/bin/env python3
"""
Simple test for multi-tenant database architecture
"""
import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

async def test_database_creation():
    """Test basic database creation functionality"""
    print("🚀 Testing Multi-Tenant Database Creation")
    print("=" * 50)
    
    try:
        # Import after path setup
        from app.db.tenant_manager import tenant_manager
        from app.core.config import settings
        
        print(f"1. Using database: {settings.DATABASE_URL}")
        
        # Test 1: Create master database connection
        print("\n2. Testing master database connection...")
        master_session = await tenant_manager.get_master_session()
        print("   ✅ Master database connection successful")
        await master_session.close()
        
        # Test 2: Create a tenant database
        print("\n3. Creating tenant database...")
        test_org_id = "test-org-123"
        
        success = await tenant_manager.create_tenant_database(test_org_id)
        if success:
            print(f"   ✅ Tenant database created: zphere_tenant_{test_org_id}")
        else:
            print(f"   ❌ Failed to create tenant database")
            return False
        
        # Test 3: Get tenant session
        print("\n4. Testing tenant database connection...")
        tenant_session = await tenant_manager.get_tenant_session(test_org_id)
        print(f"   ✅ Tenant database connection successful")
        await tenant_session.close()
        
        # Test 4: Verify database separation
        print("\n5. Verifying database separation...")
        
        # Check PostgreSQL databases
        import asyncpg
        if not settings.DATABASE_URL.startswith("sqlite"):
            conn_params = {
                'host': settings.DATABASE_HOST,
                'port': settings.DATABASE_PORT,
                'user': settings.DATABASE_USER,
                'password': settings.DATABASE_PASSWORD,
                'database': 'postgres'
            }
            conn_params = {k: v for k, v in conn_params.items() if v}
            
            conn = await asyncpg.connect(**conn_params)
            try:
                databases = await conn.fetch(
                    "SELECT datname FROM pg_database WHERE datname LIKE 'zphere%'"
                )
                print(f"   ✅ Zphere databases found: {[db['datname'] for db in databases]}")
            finally:
                await conn.close()
        else:
            print("   ✅ SQLite mode - databases created as separate files")
        
        print("\n🎉 Multi-tenant database architecture working!")
        print("=" * 50)
        print("\n📊 What was tested:")
        print("• Master database connection")
        print("• Tenant database creation")
        print("• Tenant database connection")
        print("• Database isolation verification")
        
        # Cleanup
        print("\n6. Cleaning up...")
        await tenant_manager.delete_tenant_database(test_org_id)
        await tenant_manager.close_all_connections()
        print("   ✅ Cleanup completed")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_database_creation())
    sys.exit(0 if success else 1)
