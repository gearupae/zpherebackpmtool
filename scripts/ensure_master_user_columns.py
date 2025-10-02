#!/usr/bin/env python3
import asyncio
from sqlalchemy import text
import os, sys

# Ensure project root (parent of scripts/) is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.db.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS address VARCHAR(255);"))
            await session.commit()
            print("Ensured users.address column exists in master DB.")
        except Exception as e:
            await session.rollback()
            print(f"Error ensuring column: {e}")

if __name__ == "__main__":
    asyncio.run(main())

