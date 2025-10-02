#!/usr/bin/env python3
"""Initialize the database for ZSphere"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.db.database import engine
from app.models.base import Base

async def init_database():
    """Create all database tables"""
    async with engine.begin() as conn:
        # Drop all tables first (for clean slate)
        await conn.run_sync(Base.metadata.drop_all)
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_database())
