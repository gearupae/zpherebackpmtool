from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from datetime import datetime, timedelta
import uuid

from ....api.deps_tenant import get_tenant_db
from ....models.user import User
from ....models.organization import Organization
from ....models.notification import Notification, NotificationPriority, NotificationType, NotificationPreference
from ....schemas.notification import Notification as NotificationResponse, NotificationCreate, NotificationUpdate
from ...deps_tenant import get_current_active_user_master, get_current_organization_master
from .websockets import send_notification as send_ws_notification

router = APIRouter()


@router.get("/", response_model=dict)
async def get_notifications(
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    priority: Optional[NotificationPriority] = Query(None),
    notification_type: Optional[NotificationType] = Query(None),
) -> Any:
    """Get user notifications from database"""
    
    # Build query for user's notifications
    query = select(Notification).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.organization_id == current_user.organization_id
        )
    )
    
    # Apply filters
    if unread_only:
        query = query.where(Notification.is_read == False)
        
    if priority:
        query = query.where(Notification.priority == priority)
        
    if notification_type:
        query = query.where(Notification.notification_type == notification_type)
    
    # Filter out expired notifications
    query = query.where(
        or_(
            Notification.expires_at.is_(None),
            Notification.expires_at > datetime.utcnow()
        )
    )
    
    # Count total notifications for pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Count unread notifications
    unread_query = select(func.count(Notification.id)).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.organization_id == current_user.organization_id,
            Notification.is_read == False,
            or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.utcnow()
            )
        )
    )
    unread_result = await db.execute(unread_query)
    unread_count = unread_result.scalar() or 0
    
    # Apply ordering and pagination
    query = query.order_by(
        Notification.priority.desc(),
        desc(Notification.created_at)
    )
    query = query.offset((page - 1) * size).limit(size)
    
    # Execute query
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    # Convert to response format
    notifications_data = []
    for notification in notifications:
        notifications_data.append({
            "id": notification.id,
            "type": notification.notification_type.value,  # backward-compat alias
            "notification_type": notification.notification_type.value,
            "title": notification.title,
            "message": notification.message,
            "short_description": notification.short_description,
            "priority": notification.priority.value,
            "category": notification.category,
            "is_read": notification.is_read,
            "read_at": notification.read_at.isoformat() if notification.read_at else None,
            "is_dismissed": notification.is_dismissed,
            "action_required": notification.action_required,
            "relevance_score": notification.relevance_score,
            "context_data": notification.context_data or {},
            "tags": notification.tags or [],
            "created_at": notification.created_at.isoformat(),
            "updated_at": notification.updated_at.isoformat(),
            "project_id": notification.project_id,
            "task_id": notification.task_id,
            "source": notification.source,
            "thread_id": notification.thread_id,
        })
    
    pages = (total + size - 1) // size
    
    return {
        "notifications": notifications_data,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
        "unread_count": unread_count
    }


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Mark notification as read"""
    
    # Find the notification
    query = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
            Notification.organization_id == current_user.organization_id
        )
    )
    
    result = await db.execute(query)
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Mark as read
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    
    await db.commit()
    
    return {
        "message": "Notification marked as read",
        "notification_id": notification_id
    }


@router.put("/mark-all-read")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Mark all notifications as read"""
    
    # Update all unread notifications for the user
    from sqlalchemy import update
    
    stmt = update(Notification).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.organization_id == current_user.organization_id,
            Notification.is_read == False
        )
    ).values(
        is_read=True,
        read_at=datetime.utcnow()
    )
    
    result = await db.execute(stmt)
    await db.commit()
    
    return {
        "message": "All notifications marked as read",
        "updated_count": result.rowcount
    }


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Delete a notification"""
    
    # Find the notification
    query = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
            Notification.organization_id == current_user.organization_id
        )
    )
    
    result = await db.execute(query)
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Delete the notification
    await db.delete(notification)
    await db.commit()
    
    return {
        "message": "Notification deleted",
        "notification_id": notification_id
    }


@router.get("/settings")
async def get_notification_settings(
    current_user: User = Depends(get_current_active_user_master),
) -> Any:
    """Get user notification preferences"""
    
    # Get from user preferences
    notification_settings = current_user.notification_settings or {}
    
    return {
        "email_notifications": notification_settings.get("email_notifications", True),
        "task_assignments": notification_settings.get("task_assignments", True),
        "project_updates": notification_settings.get("project_updates", True),
        "invoice_updates": notification_settings.get("invoice_updates", True),
        "team_mentions": notification_settings.get("team_mentions", True),
        "due_date_reminders": notification_settings.get("due_date_reminders", True),
        "weekly_summary": notification_settings.get("weekly_summary", False)
    }


@router.put("/settings")
async def update_notification_settings(
    settings_data: dict,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update user notification preferences"""
    
    # Update user notification settings
    current_settings = current_user.notification_settings or {}
    current_settings.update(settings_data)
    current_user.notification_settings = current_settings
    
    await db.commit()
    
    return {
        "message": "Notification settings updated",
        "settings": current_settings
    }


# Helper functions to create and manage notifications

@router.post("/")
async def create_notification_endpoint(
    notification_data: NotificationCreate,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new notification (for testing or admin purposes)"""
    
    notification = await create_notification(
        user_id=notification_data.user_id,
        organization_id=current_user.organization_id,
        notification_type=notification_data.notification_type,
        title=notification_data.title,
        message=notification_data.message,
        context_data=notification_data.context_data,
        priority=notification_data.priority,
        db=db
    )
    
    return notification


async def create_notification(
    user_id: str,
    organization_id: str,
    notification_type: NotificationType,
    title: str,
    message: str,
    context_data: dict = None,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    project_id: str = None,
    task_id: str = None,
    source: str = None,
    db: AsyncSession = None
):
    """Create a new notification in the database"""
    
    notification = Notification(
        id=str(uuid.uuid4()),
        user_id=user_id,
        organization_id=organization_id,
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        context_data=context_data or {},
        project_id=project_id,
        task_id=task_id,
        source=source or "system",
        is_read=False,
        auto_generated=True,
        relevance_score=0.8,  # Default high relevance for system notifications
        delivery_channels=["in_app"],
        tags=[],
    )
    
    if db:
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        
        # Send real-time notification via WebSocket (non-blocking best-effort)
        try:
            await send_ws_notification(
                user_id,
                organization_id,
                {
                    "id": notification.id,
                    "type": notification.notification_type.value,
                    "notification_type": notification.notification_type.value,
                    "title": notification.title,
                    "message": notification.message,
                    "priority": notification.priority.value,
                    "is_read": notification.is_read,
                    "created_at": notification.created_at.isoformat(),
                    "project_id": notification.project_id,
                    "task_id": notification.task_id,
                    "source": notification.source,
                    "thread_id": notification.thread_id,
                },
            )
        except Exception:
            # Ignore WS errors to avoid affecting API response
            pass
        # TODO: Schedule email/push notifications based on user preferences
    
    return {
        "id": notification.id,
        "user_id": notification.user_id,
        "type": notification.notification_type.value,
        "title": notification.title,
        "message": notification.message,
        "priority": notification.priority.value,
        "context_data": notification.context_data,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat()
    }
