#!/usr/bin/env python3
"""
Show existing tenant credentials
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Database URL
DATABASE_URL = "sqlite+aiosqlite:///./zphere.db"

async def show_credentials():
    """Show existing credentials"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            from app.models.user import User
            from app.models.organization import Organization
            from app.models.project import Project
            from app.models.customer import Customer
            
            # Get organizations
            org_result = await session.execute(select(Organization))
            organizations = org_result.scalars().all()
            
            if not organizations:
                print("❌ No organizations found!")
                return
            
            print("🏢 ZPHERE TENANT CREDENTIALS")
            print("=" * 50)
            
            for org in organizations:
                print(f"\n🏢 ORGANIZATION: {org.name}")
                print(f"   ID: {org.id}")
                print(f"   Slug: {org.slug}")
                print(f"   Tier: {org.subscription_tier}")
                
                # Get users for this organization
                user_result = await session.execute(
                    select(User).where(User.organization_id == org.id)
                )
                users = user_result.scalars().all()
                
                if users:
                    print(f"\n   👤 USERS:")
                    for user in users:
                        print(f"      📧 {user.email}")
                        print(f"         Username: {user.username}")
                        print(f"         Role: {user.role}")
                        print(f"         Status: {user.status}")
                        if user.email == "admin@zphere.com":
                            print(f"         🔑 Password: admin123")
                        print()
                
                # Get projects count
                project_result = await session.execute(
                    select(Project).where(Project.organization_id == org.id)
                )
                project_count = len(project_result.scalars().all())
                
                # Get customers count
                customer_result = await session.execute(
                    select(Customer).where(Customer.organization_id == org.id)
                )
                customer_count = len(customer_result.scalars().all())
                
                print(f"   📊 DATA:")
                print(f"      Projects: {project_count}")
                print(f"      Customers: {customer_count}")
            
            print(f"\n🌐 API ACCESS:")
            print(f"   Base URL: http://localhost:8000/api/v1")
            print(f"   Login: POST /auth/login")
            print(f"   Docs: http://localhost:8000/api/v1/docs")
            
            print(f"\n🔧 TO START THE BACKEND:")
            print(f"   cd backend")
            print(f"   source venv/bin/activate")
            print(f"   python run.py")
            
            print(f"\n💡 LOGIN PAYLOAD EXAMPLE:")
            print(f'   {{')
            print(f'     "username": "admin",')
            print(f'     "password": "admin123"')
            print(f'   }}')
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(show_credentials())
