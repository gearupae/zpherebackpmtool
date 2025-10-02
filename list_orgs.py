#!/usr/bin/env python3
"""
List all organizations in the database
"""
import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

async def list_organizations():
    """List all organizations in the database"""
    try:
        from app.db.database import AsyncSessionLocal
        from app.models.organization import Organization
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Organization))
            orgs = result.scalars().all()
            
            print("\n🏢 Organizations in the database:")
            print("=" * 50)
            
            for org in orgs:
                print(f"ID: {org.id}")
                print(f"Name: {org.name}")
                print(f"Slug: {org.slug}")
                print(f"Active: {org.is_active}")
                print(f"Settings: {org.settings}")
                print("-" * 50)
            
            return True
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(list_organizations())
