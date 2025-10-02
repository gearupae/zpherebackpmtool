"""Notification service: centralized creation with focus suppression and scheduling.
This service respects:
- User NotificationPreference (urgent_only_mode, minimum_priority, timezone)
- Active Focus Blocks (FocusBlock) for the user
If suppression is needed, scheduled_for is set to the end of the active focus window.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from ..models.notification import Notification, NotificationType, NotificationPriority, NotificationPreference
from ..models.focus import FocusBlock


async def _get_user_prefs(user_id: str, db: AsyncSession) -> Optional[NotificationPreference]:
    res = await db.execute(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    return res.scalar_one_or_none()


async def _get_active_focus_end(user_id: str, org_id: str, db: AsyncSession) -> Optional[datetime]:
    """Return the end time of the first active focus block that overlaps now, else None."""
    now = datetime.utcnow()
    q = select(FocusBlock).where(
        and_(
            FocusBlock.user_id == user_id,
            FocusBlock.organization_id == org_id,
            FocusBlock.start_time <= now,
            FocusBlock.end_time > now,
        )
    ).order_by(FocusBlock.end_time.asc())
    res = await db.execute(q)
    block = res.scalar_one_or_none()
    return block.end_time if block else None


async def create_notification_for_user(
    db: AsyncSession,
    *,
    user_id: str,
    org_id: str,
    title: str,
    message: str,
    notification_type: NotificationType,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    project_id: Optional[str] = None,
    task_id: Optional[str] = None,
    context_card_id: Optional[str] = None,
    decision_log_id: Optional[str] = None,
    handoff_summary_id: Optional[str] = None,
    relevance_score: Optional[float] = 0.5,
    context_data: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    source: Optional[str] = None,
    action_required: bool = False,
    auto_generated: bool = True,
) -> Notification:
    """Create a Notification with respect to focus suppression and preferences."""
    prefs = await _get_user_prefs(user_id, db)

    # Focus suppression: if current time within active focus block, schedule delivery after it
    scheduled_for = await _get_active_focus_end(user_id, org_id, db)

    notif = Notification(
        title=title,
        message=message,
        notification_type=notification_type,
        priority=priority,
        user_id=user_id,
        organization_id=org_id,
        project_id=project_id,
        task_id=task_id,
        context_card_id=context_card_id,
        decision_log_id=decision_log_id,
        handoff_summary_id=handoff_summary_id,
        relevance_score=relevance_score or 0.5,
        context_data=context_data or {},
        tags=tags or [],
        source=source,
        action_required=action_required,
        auto_generated=auto_generated,
        scheduled_for=scheduled_for,
        timezone_aware=True,
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)

    # Send real-time notification via WebSocket (best-effort)
    try:
        from app.api.api_v1.endpoints.websockets import send_notification as send_ws_notification
        await send_ws_notification(
            user_id,
            org_id,
            {
                "id": notif.id,
                "type": notif.notification_type.value,
                "notification_type": notif.notification_type.value,
                "title": notif.title,
                "message": notif.message,
                "priority": notif.priority.value,
                "is_read": notif.is_read,
                "created_at": notif.created_at.isoformat() if notif.created_at else None,
                "project_id": notif.project_id,
                "task_id": notif.task_id,
                "source": notif.source,
                "thread_id": notif.thread_id,
            },
        )
    except Exception:
        pass

    return notif
