#!/usr/bin/env python3
"""
List tenant organizations and their admin users (emails/usernames), plus a safe DB DSN template.
No passwords are printed. Intended for read-only inspection.
"""
import asyncio
import os
import sys
import json
from sqlalchemy import select

# Ensure backend modules are importable
THIS_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(THIS_DIR, '..'))
sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings  # noqa: E402
from app.db.database import AsyncSessionLocal  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.user import User  # noqa: E402
# Ensure goal association table is registered before mapper config
import app.models.goal  # noqa: F401


def build_safe_dsn_template() -> str:
    try:
        from sqlalchemy.engine import make_url
        url = make_url(settings.DATABASE_URL)
        host = url.host or 'localhost'
        port = url.port or 5432
        drivername = 'postgresql+asyncpg' if url.drivername.startswith('postgresql') else url.drivername
        return f"{drivername}://{{DB_USER}}:{{DB_PASSWORD}}@{host}:{port}/zphere_tenant_{{organization_id}}"
    except Exception:
        return "postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@localhost:5432/zphere_tenant_{organization_id}"


async def main():
    output = {
        "dsn_template": build_safe_dsn_template(),
        "tenants": []
    }

    async with AsyncSessionLocal() as session:
        # List organizations
        orgs = (await session.execute(select(Organization))).scalars().all()
        for org in orgs:
            # Admin users for this org (do not include passwords)
            admins = (await session.execute(
                select(User).where((User.organization_id == org.id) & (User.role == 'ADMIN'))
            )).scalars().all()

            output["tenants"].append({
                "organization": {
                    "id": org.id,
                    "slug": org.slug,
                    "name": org.name,
                    "active": bool(getattr(org, 'is_active', True))
                },
                "admin_users": [
                    {
                        "email": u.email,
                        "username": u.username,
                        "role": u.role,
                        "status": getattr(u, 'status', None)
                    }
                    for u in admins
                ]
            })

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    # Run from repo root so pydantic reads the .env there
    repo_root = os.path.abspath(os.path.join(BACKEND_DIR, '..'))
    os.chdir(repo_root)
    asyncio.run(main())

