"""Simple scheduler service for digests and delayed notification delivery.
Runs background loops without external dependencies.
"""
import asyncio
from datetime import datetime, timedelta, time
from typing import Optional
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ..db.tenant_manager import tenant_manager
from ..models.user import User
from ..models.notification import Notification, NotificationType, NotificationPriority
from ..models.notification import NotificationPreference
from ..services.notification_service import create_notification_for_user
from ..api.api_v1.endpoints.smart_notifications import generate_notification_digest

_SCHEDULER_TASK = None


async def _run_digest_loop():
    """Every 5 minutes, generate digests for users whose local time matches their digest schedule."""
    while True:
        try:
            # List all active organizations from master DB
            master_session: AsyncSession = await tenant_manager.get_master_session()
            try:
                from ..models.organization import Organization
                orgs_res = await master_session.execute(select(Organization).where(Organization.is_active == True))
                orgs = orgs_res.scalars().all()
            finally:
                await master_session.close()

            for org in orgs:
                # Tenant session per org
                session: AsyncSession = await tenant_manager.get_tenant_session(org.id)
                try:
                    # Fetch users and their prefs
                    q = select(User, NotificationPreference).join(
                        NotificationPreference, NotificationPreference.user_id == User.id, isouter=True
                    ).where(User.organization_id == org.id, User.is_active == True)
                    res = await session.execute(q)
                    rows = res.all()

                    now_utc = datetime.utcnow()
                    for (user, prefs) in rows:
                        if not prefs:
                            continue
                        # Daily digest
                        if prefs.daily_digest_enabled and prefs.daily_digest_time:
                            tz = ZoneInfo(prefs.timezone or "UTC")
                            now_local = now_utc.astimezone(tz)
                            hh, mm = map(int, prefs.daily_digest_time.split(":"))
                            target_today = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
                            if abs((now_local - target_today).total_seconds()) <= 240:  # within 4 minutes
                                # Generate digest for today (local date)
                                period_start_local = target_today.replace(hour=0, minute=0)
                                period_end_local = period_start_local + timedelta(days=1)
                                period_start = period_start_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
                                period_end = period_end_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
                                digest = await generate_notification_digest(user.id, org.id, "daily", period_start, period_end, session)
                                # Persist a notification summarizing the digest
                                await create_notification_for_user(
                                    session,
                                    user_id=user.id,
                                    org_id=org.id,
                                    title="Daily Digest",
                                    message=f"You have {digest.total_notifications} notifications today.",
                                    notification_type=NotificationType.REMINDER,
                                    priority=NotificationPriority.NORMAL,
                                    context_data={
                                        "digest_type": "daily",
                                        "period_start": digest.period_start.isoformat(),
                                        "period_end": digest.period_end.isoformat(),
                                        "urgent_count": len(digest.urgent_notifications),
                                        "project_summaries": digest.project_summaries,
                                    },
                                    auto_generated=True,
                                    source="scheduler_daily_digest",
                                )
                        # Weekly digests similar (optional): left for future extension
                finally:
                    await session.close()
        except Exception:
            # Best-effort; never crash loop
            pass
        await asyncio.sleep(300)  # 5 minutes


async def start_scheduler():
    global _SCHEDULER_TASK
    if _SCHEDULER_TASK is None or _SCHEDULER_TASK.done():
        _SCHEDULER_TASK = asyncio.create_task(_run_digest_loop())
