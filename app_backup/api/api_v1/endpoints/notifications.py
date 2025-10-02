from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from datetime import datetime, timedelta
import uuid

from ....db.database import get_db
from ....models.user import User
from ....models.organization import Organization
from ...deps import get_current_active_user, get_current_organization

router = APIRouter()


@router.get("/")
async def get_notifications(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
) -> Any:
    """Get user notifications"""
    
    # TODO: Implement actual notifications table and queries
    # For now, return mock data
    
    mock_notifications = [
        {
            "id": str(uuid.uuid4()),
            "type": "task_assigned",
            "title": "New task assigned",
            "message": "You have been assigned to task 'Complete project documentation'",
            "is_read": False,
            "created_at": datetime.utcnow().isoformat(),
            "data": {
                "task_id": "task-123",
                "project_id": "project-456"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "type": "project_update",
            "title": "Project status updated",
            "message": "Project 'Website Redesign' status changed to In Progress",
            "is_read": True,
            "created_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "data": {
                "project_id": "project-456"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "type": "invoice_paid",
            "title": "Invoice payment received",
            "message": "Invoice INV-2024-001 has been paid",
            "is_read": False,
            "created_at": (datetime.utcnow() - timedelta(days=1)).isoformat(),
            "data": {
                "invoice_id": "invoice-789"
            }
        }
    ]
    
    # Filter unread if requested
    if unread_only:
        mock_notifications = [n for n in mock_notifications if not n["is_read"]]
    
    # Apply pagination
    start_idx = (page - 1) * size
    end_idx = start_idx + size
    paginated_notifications = mock_notifications[start_idx:end_idx]
    
    return {
        "notifications": paginated_notifications,
        "total": len(mock_notifications),
        "page": page,
        "size": size,
        "pages": (len(mock_notifications) + size - 1) // size,
        "unread_count": len([n for n in mock_notifications if not n["is_read"]])
    }


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Mark notification as read"""
    
    # TODO: Update notification in database
    return {
        "message": "Notification marked as read",
        "notification_id": notification_id
    }


@router.put("/mark-all-read")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Mark all notifications as read"""
    
    # TODO: Update all user notifications in database
    return {
        "message": "All notifications marked as read"
    }


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Delete a notification"""
    
    # TODO: Delete notification from database
    return {
        "message": "Notification deleted"
    }


@router.get("/settings")
async def get_notification_settings(
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
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


# Helper function to create notifications (to be used by other endpoints)
async def create_notification(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    data: dict = None,
    db: AsyncSession = None
):
    """Create a new notification for a user"""
    
    # TODO: Implement actual notification creation in database
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "data": data or {},
        "is_read": False,
        "created_at": datetime.utcnow()
    }
    
    # TODO: Save to database
    # TODO: Send real-time notification via WebSocket
    
    return notification
