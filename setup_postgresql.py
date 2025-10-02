#!/usr/bin/env python3
"""
Setup script to migrate from SQLite to PostgreSQL and create users
"""
import asyncio
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from passlib.context import CryptContext
import os

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def setup_postgresql():
    print("🐘 Setting up PostgreSQL for Zphere...")
    print("=" * 50)
    
    # Get PostgreSQL connection details
    db_user = input("PostgreSQL username (default: postgres): ") or "postgres"
    db_password = input("PostgreSQL password: ")
    db_host = input("PostgreSQL host (default: localhost): ") or "localhost"
    db_port = input("PostgreSQL port (default: 5432): ") or "5432"
    db_name = input("Database name (default: zphere_db): ") or "zphere_db"
    
    # Construct PostgreSQL URL
    DATABASE_URL = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    print(f"\n📊 Database URL: postgresql+asyncpg://{db_user}:***@{db_host}:{db_port}/{db_name}")
    
    try:
        # Create async engine
        engine = create_async_engine(DATABASE_URL, echo=True)
        
        # Test connection
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ Connected to PostgreSQL: {version}")
        
        # Create session factory
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        # Import models to create tables
        print("\n📋 Creating database tables...")
        from app.models.base import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables created successfully")
        
        # Create demo users
        print("\n👥 Creating demo users...")
        async with async_session() as session:
            from app.models.user import User, UserRole, UserStatus
            from app.models.organization import Organization
            
            # Create organization
            organization = Organization(
                id=str(uuid.uuid4()),
                name="Demo Organization",
                slug="demo-org",
                description="Demo organization for testing",
                domain="demo.com",
                is_active=True,
                subscription_tier="premium",
                max_users=50,
                max_projects=100,
                database_created=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(organization)
            await session.flush()
            
            # Create admin user
            admin_user = User(
                id=str(uuid.uuid4()),
                email="admin@zphere.com",
                username="admin",
                first_name="Admin",
                last_name="User",
                hashed_password=pwd_context.hash("admin123"),
                organization_id=organization.id,
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                is_active=True,
                is_verified=True,
                timezone="UTC",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(admin_user)
            
            # Create tenant user
            tenant_user = User(
                id=str(uuid.uuid4()),
                email="tenant@demo.com",
                username="tenant",
                first_name="Tenant",
                last_name="User",
                hashed_password=pwd_context.hash("tenant123"),
                organization_id=organization.id,
                role=UserRole.TENANT,
                status=UserStatus.ACTIVE,
                is_active=True,
                is_verified=True,
                timezone="UTC",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(tenant_user)
            
            await session.commit()
            print("✅ Demo users created")
        
        await engine.dispose()
        
        print("\n" + "=" * 60)
        print("🎉 PostgreSQL Setup Complete!")
        print("=" * 60)
        
        print(f"\n📝 Update your backend configuration:")
        print(f"   DATABASE_URL={DATABASE_URL}")
        print(f"\n🔑 Login Credentials:")
        print(f"   Admin:  admin@zphere.com / admin123")
        print(f"   Tenant: tenant@demo.com / tenant123")
        print(f"\n⚠️  Remember to restart your backend server!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error setting up PostgreSQL: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(setup_postgresql())
    if success:
        print("\n✅ Ready to use PostgreSQL!")
    else:
        print("\n❌ Setup failed. Please check your PostgreSQL connection.")
