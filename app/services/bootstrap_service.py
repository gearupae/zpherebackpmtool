from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..db.database import AsyncSessionLocal
from ..models.user import User, UserRole, UserStatus
from ..models.organization import Organization
from ..core.security import get_password_hash
import uuid

async def ensure_platform_admin() -> None:
    """Ensure a platform admin organization and user exist.
    - Organization: Zphere Platform Administration (slug: zphere-admin)
    - User: admin@zphere.com / admin123
    Safe to run multiple times (idempotent).
    """
    async with AsyncSessionLocal() as db:
        try:
            # Check if admin user exists
            res = await db.execute(select(User).where(User.email == "admin@zphere.com"))
            existing = res.scalar_one_or_none()
            if existing:
                return

            # Create platform admin org
            admin_org_id = str(uuid.uuid4())
            org = Organization(
                id=admin_org_id,
                name="Zphere Platform Administration",
                slug="zphere-admin",
                is_active=True,
                subscription_tier="enterprise",
                max_users=1000,
                max_projects=1000,
                settings={"is_platform_admin": True}
            )
            db.add(org)

            # Create platform admin user
            admin_user = User(
                id=str(uuid.uuid4()),
                email="admin@zphere.com",
                username="platform_admin",
                first_name="Platform",
                last_name="Administrator",
                hashed_password=get_password_hash("admin123"),
                organization_id=admin_org_id,
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
                status=UserStatus.ACTIVE
            )
            db.add(admin_user)
            await db.commit()
        except Exception:
            await db.rollback()
            # Do not raise during startup; leave to manual seeding
            pass
