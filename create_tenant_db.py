#!/usr/bin/env python3
"""
Create a tenant database for an existing organization
"""
import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

async def create_tenant_database():
    """Create a tenant database for an existing organization"""
    print("🏢 Creating Tenant Database")
    print("=" * 50)
    
    try:
        from app.db.tenant_manager import tenant_manager, TenantBase
        from app.models.organization import Organization
        from sqlalchemy import select, text
        
        # Get organization ID from command line or use default
        if len(sys.argv) > 1:
            org_id = sys.argv[1]
        else:
            org_id = "0540fdd7-7b68-4285-9763-d4b6f65f3821"  # Default organization ID
        
        # Get master session
        master_session = await tenant_manager.get_master_session()
        
        try:
            # Check if organization exists
            result = await master_session.execute(
                select(Organization).where(Organization.id == org_id)
            )
            org = result.scalar_one_or_none()
            
            if not org:
                print(f"❌ Organization with ID {org_id} not found")
                return False
            
            print(f"✅ Found organization: {org.name} (ID: {org.id})")
            
            # Create tenant database
            print(f"📦 Creating tenant database for {org.name}...")
            success = await tenant_manager.create_tenant_database(org.id)
            
            if success:
                print(f"✅ Successfully created tenant database: zphere_tenant_{org.id}")
                
                # Update organization settings to mark database as created
                if not org.settings:
                    org.settings = {}
                org.settings["database_created"] = True
                org.settings["database_name"] = f"zphere_tenant_{org.id}"
                await master_session.commit()
                print(f"✅ Updated organization settings")
                
                # Initialize tenant database with TenantBase models
                print(f"📝 Initializing tenant database schema...")
                
                # Import tenant models
                from app.models.tenant.customer import Customer
                
                # Create engine and create tables
                engine = tenant_manager._get_tenant_engine(org.id)
                async with engine.begin() as conn:
                    # Drop tables if they exist
                    await conn.run_sync(lambda sync_conn: sync_conn.execute(text("DROP TABLE IF EXISTS tenant_customers CASCADE")))
                    
                    # Create tables
                    await conn.run_sync(TenantBase.metadata.create_all)
                
                tenant_session = await tenant_manager.get_tenant_session(org.id)
                
                # Create sample customers
                sample_customers = [
                    Customer(
                        first_name="John",
                        last_name="Doe",
                        email="john.doe@example.com",
                        company_name="Example Corp",
                        phone="+1-555-1234",
                        is_active=True,
                        customer_type="client"
                    ),
                    Customer(
                        first_name="Jane",
                        last_name="Smith",
                        email="jane.smith@acme.com",
                        company_name="Acme Inc",
                        phone="+1-555-5678",
                        is_active=True,
                        customer_type="client"
                    ),
                    Customer(
                        first_name="Robert",
                        last_name="Johnson",
                        email="robert@techinc.com",
                        company_name="Tech Inc",
                        phone="+1-555-9012",
                        is_active=True,
                        customer_type="prospect"
                    )
                ]
                
                for customer in sample_customers:
                    tenant_session.add(customer)
                
                await tenant_session.commit()
                await tenant_session.close()
                print(f"✅ Tenant database schema initialized with sample data")
                
                return True
            else:
                print(f"❌ Failed to create tenant database")
                return False
            
        except Exception as e:
            await master_session.rollback()
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await master_session.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Close all connections
        await tenant_manager.close_all_connections()

if __name__ == "__main__":
    success = asyncio.run(create_tenant_database())
    sys.exit(0 if success else 1)
