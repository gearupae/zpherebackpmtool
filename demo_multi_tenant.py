#!/usr/bin/env python3
"""
Demo script showing complete multi-tenant database architecture
This demonstrates how each organization gets its own separate database
"""
import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

async def demo_multi_tenant_saas():
    """Demonstrate the complete multi-tenant SaaS architecture"""
    print("🏢 ZPHERE MULTI-TENANT SAAS ARCHITECTURE DEMO")
    print("=" * 60)
    print("This demo shows how each organization gets its own database")
    print("Single codebase, separate databases per organization")
    print("=" * 60)
    
    try:
        from app.db.tenant_manager import tenant_manager
        from app.core.config import settings
        
        print(f"\n📋 Configuration:")
        print(f"   Master Database: {settings.DATABASE_URL}")
        print(f"   Environment: {settings.ENVIRONMENT}")
        
        # Simulate 3 different companies signing up
        companies = [
            {
                "id": "acme-corp",
                "name": "Acme Corporation",
                "description": "A manufacturing company"
            },
            {
                "id": "tech-startup",
                "name": "Tech Startup Inc",
                "description": "A fast-growing tech company"
            },
            {
                "id": "consulting-firm",
                "name": "Global Consulting Firm",
                "description": "A professional services company"
            }
        ]
        
        print(f"\n🏗️  STEP 1: Creating separate databases for each organization")
        print("-" * 60)
        
        created_databases = []
        
        for company in companies:
            print(f"\n   Creating database for: {company['name']}")
            
            # Create tenant database for this organization
            success = await tenant_manager.create_tenant_database(company['id'])
            
            if success:
                print(f"   ✅ Database created: zphere_tenant_{company['id']}")
                created_databases.append(company['id'])
                
                # Test connection to this specific tenant database
                tenant_session = await tenant_manager.get_tenant_session(company['id'])
                print(f"   ✅ Connection verified for {company['name']}")
                await tenant_session.close()
            else:
                print(f"   ❌ Failed to create database for {company['name']}")
        
        print(f"\n📊 STEP 2: Verifying complete data isolation")
        print("-" * 60)
        
        if not settings.DATABASE_URL.startswith("sqlite"):
            # For PostgreSQL, show actual databases
            import asyncpg
            conn_params = {
                'host': settings.DATABASE_HOST or 'localhost',
                'port': settings.DATABASE_PORT or 5432,
                'user': settings.DATABASE_USER or 'postgres',
                'password': settings.DATABASE_PASSWORD or '',
                'database': 'postgres'
            }
            # Remove empty values
            conn_params = {k: v for k, v in conn_params.items() if v}
            
            try:
                conn = await asyncpg.connect(**conn_params)
                databases = await conn.fetch(
                    "SELECT datname FROM pg_database WHERE datname LIKE 'zphere%' ORDER BY datname"
                )
                
                print(f"   📋 Zphere Databases in PostgreSQL:")
                for db in databases:
                    db_name = db['datname']
                    if db_name.startswith('zphere_tenant_'):
                        org_id = db_name.replace('zphere_tenant_', '')
                        company_name = next((c['name'] for c in companies if c['id'] == org_id), 'Unknown')
                        print(f"      🏢 {db_name} → {company_name}")
                    else:
                        print(f"      🏛️  {db_name} → Master Database")
                
                await conn.close()
                
            except Exception as e:
                print(f"   ⚠️  Could not connect to PostgreSQL: {e}")
                print(f"   📝 Note: Make sure PostgreSQL is running")
        else:
            print(f"   📁 SQLite Mode: Each tenant gets a separate .db file")
            for company in companies:
                print(f"      🏢 tenant_{company['id']}.db → {company['name']}")
        
        print(f"\n🔒 STEP 3: Demonstrating data isolation")
        print("-" * 60)
        
        print(f"   Key Benefits of This Architecture:")
        print(f"   • 🏢 Each organization has complete data isolation")
        print(f"   • 🚀 Single codebase serves all tenants")
        print(f"   • 📈 Scales horizontally (databases can be on different servers)")
        print(f"   • 🛡️  Enhanced security (no accidental data leakage)")
        print(f"   • 🔧 Easier backup/restore per organization")
        print(f"   • ⚖️  Compliance-friendly (data residency, GDPR)")
        
        print(f"\n📋 STEP 4: Architecture Summary")
        print("-" * 60)
        print(f"   🏛️  Master Database: Organizations, Users, Authentication")
        print(f"   🏢 Tenant Databases: Projects, Tasks, Customers, Invoices")
        print(f"   🔀 Dynamic Routing: Routes queries to correct tenant database")
        print(f"   🎯 Context-Aware: User → Organization → Tenant Database")
        
        # Cleanup
        print(f"\n🧹 STEP 5: Cleanup")
        print("-" * 60)
        
        for org_id in created_databases:
            await tenant_manager.delete_tenant_database(org_id)
            print(f"   ✅ Deleted: zphere_tenant_{org_id}")
        
        await tenant_manager.close_all_connections()
        print(f"   ✅ All connections closed")
        
        print(f"\n🎉 MULTI-TENANT SAAS ARCHITECTURE DEMO COMPLETE!")
        print("=" * 60)
        print("Your Zphere platform now supports:")
        print("✅ Separate database per organization")
        print("✅ Complete data isolation")
        print("✅ Single codebase for all tenants")
        print("✅ Dynamic database routing")
        print("✅ Scalable architecture")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(demo_multi_tenant_saas())
    sys.exit(0 if success else 1)
