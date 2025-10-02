from typing import List
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

async def ensure_task_columns():
    """Best-effort: ensure newly added task columns exist in all tenant databases.
    - visible_to_customer (BOOLEAN)
    - sprint_name (VARCHAR)
    - sprint_start_date (TIMESTAMPTZ)
    - sprint_end_date (TIMESTAMPTZ)
    - sprint_goal (TEXT)
    This function is idempotent and safe to run on startup.
    """
    try:
        from ..db.tenant_manager import tenant_manager
        from ..models.organization import Organization
        # Get all organizations from master
        master: AsyncSession = await tenant_manager.get_master_session()
        try:
            res = await master.execute(select(Organization.id))
            org_ids: List[str] = [row[0] for row in res.fetchall()]
        finally:
            await master.close()

        # For each tenant DB, attempt ALTER TABLE ... ADD COLUMN IF NOT EXISTS
        for org_id in org_ids:
            try:
                session: AsyncSession = await tenant_manager.get_tenant_session(org_id)
                try:
                    stmts = [
                        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS visible_to_customer BOOLEAN DEFAULT FALSE;",
                        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS sprint_name VARCHAR(255);",
                        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS sprint_start_date TIMESTAMPTZ;",
                        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS sprint_end_date TIMESTAMPTZ;",
                        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS sprint_goal TEXT;",
                    ]
                    for sql in stmts:
                        try:
                            await session.execute(text(sql))
                        except Exception:
                            # Best-effort; continue
                            pass
                    await session.commit()
                finally:
                    await session.close()
            except Exception:
                # Continue to next tenant
                pass
    except Exception:
        # Best-effort overall
        pass

