"""Enhanced Smart Notifications API with AI-powered features"""
from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
import json
import asyncio

# from ....db.database import get_db
from ...deps_tenant import get_tenant_db
from ....models.user import User
from ....models.organization import Organization
from ....models.notification import (
    Notification, NotificationPreference, NotificationRule, NotificationAnalytics,
    NotificationType, NotificationPriority
)
from ....schemas.notification import (
    NotificationCreate, NotificationUpdate, Notification as NotificationSchema,
    NotificationPreferenceCreate, NotificationPreferenceUpdate, 
    NotificationPreference as NotificationPreferenceSchema,
    NotificationRuleCreate, NotificationRuleUpdate,
    NotificationRule as NotificationRuleSchema,
    NotificationMarkRead, NotificationFeedback,
    NotificationSummaryResponse, FocusModeStatus, NotificationDigest,
    SmartNotificationInsights
)
from ....models.focus import FocusBlock as FocusBlockModel
from ....schemas.focus import FocusBlockCreate, FocusBlockUpdate, FocusBlock as FocusBlockSchema
from ....services.notification_service import create_notification_for_user
from zoneinfo import ZoneInfo
from ...deps import get_current_active_user, get_current_organization

router = APIRouter()


# Smart Notification Endpoints
@router.get("/", response_model=NotificationSummaryResponse)
async def get_smart_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    priority_filter: Optional[str] = Query(None),
    type_filter: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    grouped: bool = Query(True),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get smart notifications with AI-powered filtering and grouping"""
    
    # Get user preferences
    prefs = await get_user_notification_preferences(current_user.id, db)
    
    # Build base query
    query = select(Notification).options(
        selectinload(Notification.project),
        selectinload(Notification.task),
        selectinload(Notification.context_card),
        selectinload(Notification.decision_log),
        selectinload(Notification.handoff_summary)
    ).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.organization_id == current_org.id,
            or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.utcnow()
            )
        )
    )
    
    # Apply filters based on user preferences and request parameters
    conditions = []

    # Hide scheduled notifications that are in the future
    conditions.append(or_(Notification.scheduled_for.is_(None), Notification.scheduled_for <= func.now()))
    
    if unread_only:
        conditions.append(Notification.is_read == False)
    
    if priority_filter:
        try:
            priority = NotificationPriority(priority_filter.lower())
            conditions.append(Notification.priority == priority)
        except ValueError:
            pass
    
    if type_filter:
        try:
            notification_type = NotificationType(type_filter.lower())
            conditions.append(Notification.notification_type == notification_type)
        except ValueError:
            pass
    
    if project_id:
        conditions.append(Notification.project_id == project_id)
    
    # Apply AI-powered relevance filtering
    if prefs and prefs.ai_filtering_enabled:
        conditions.append(Notification.relevance_score >= prefs.relevance_threshold)
    
    # Apply minimum priority filter from preferences
    if prefs and prefs.urgent_only_mode:
        conditions.append(Notification.priority.in_([
            NotificationPriority.URGENT, NotificationPriority.CRITICAL
        ]))
    elif prefs and prefs.minimum_priority:
        priority_order = {
            NotificationPriority.LOW: 0,
            NotificationPriority.NORMAL: 1, 
            NotificationPriority.HIGH: 2,
            NotificationPriority.URGENT: 3,
            NotificationPriority.CRITICAL: 4
        }
        min_level = priority_order.get(prefs.minimum_priority, 0)
        allowed_priorities = [p for p, level in priority_order.items() if level >= min_level]
        conditions.append(Notification.priority.in_(allowed_priorities))
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Order by priority and relevance score
    query = query.order_by(
        desc(Notification.priority),
        desc(Notification.relevance_score),
        desc(Notification.created_at)
    )
    
    # Get total count for pagination
    count_query = select(func.count(Notification.id)).where(query.whereclause)
    total_result = await db.execute(count_query)
    total_count = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    # Calculate summary stats
    unread_count_query = select(func.count(Notification.id)).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
            Notification.organization_id == current_org.id
        )
    )
    unread_result = await db.execute(unread_count_query)
    unread_count = unread_result.scalar()
    
    urgent_count_query = select(func.count(Notification.id)).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
            Notification.priority.in_([NotificationPriority.URGENT, NotificationPriority.CRITICAL]),
            Notification.organization_id == current_org.id
        )
    )
    urgent_result = await db.execute(urgent_count_query)
    urgent_count = urgent_result.scalar()
    
    # Group notifications if requested
    grouped_notifications = None
    if grouped and prefs and prefs.context_aware_grouping:
        grouped_notifications = await group_notifications_by_context(notifications)
    
    return NotificationSummaryResponse(
        total_notifications=total_count,
        unread_count=unread_count,
        urgent_count=urgent_count,
        notifications=[NotificationSchema.from_orm(n) for n in notifications],
        grouped_notifications=grouped_notifications
    )


@router.post("/mark-read", status_code=status.HTTP_200_OK)
async def mark_notifications_read(
    mark_data: NotificationMarkRead,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Mark multiple notifications as read"""
    
    # Update notifications
    update_query = select(Notification).where(
        and_(
            Notification.id.in_(mark_data.notification_ids),
            Notification.user_id == current_user.id
        )
    )
    result = await db.execute(update_query)
    notifications = result.scalars().all()
    
    for notification in notifications:
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": f"Marked {len(notifications)} notifications as read"}


@router.post("/{notification_id}/feedback", status_code=status.HTTP_200_OK)
async def provide_notification_feedback(
    notification_id: str,
    feedback: NotificationFeedback,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Provide feedback on notification relevance and quality"""
    
    # Verify notification exists and belongs to user
    notification_query = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    result = await db.execute(notification_query)
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Create or update analytics record
    analytics_query = select(NotificationAnalytics).where(
        and_(
            NotificationAnalytics.notification_id == notification_id,
            NotificationAnalytics.user_id == current_user.id
        )
    )
    analytics_result = await db.execute(analytics_query)
    analytics = analytics_result.scalar_one_or_none()
    
    if not analytics:
        analytics = NotificationAnalytics(
            user_id=current_user.id,
            notification_id=notification_id
        )
        db.add(analytics)
    
    # Update feedback
    if feedback.relevance_feedback is not None:
        analytics.relevance_feedback = feedback.relevance_feedback
    if feedback.user_rating is not None:
        analytics.user_rating = feedback.user_rating
    if feedback.marked_as_spam:
        analytics.marked_as_spam = True
    
    await db.commit()
    
    return {"message": "Feedback recorded successfully"}


# Notification Preferences Endpoints
@router.get("/preferences", response_model=NotificationPreferenceSchema)
async def get_notification_preferences(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get user notification preferences"""
    
    prefs = await get_user_notification_preferences(current_user.id, db)
    if not prefs:
        # Create default preferences
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)
    
    return NotificationPreferenceSchema.from_orm(prefs)


@router.put("/preferences", response_model=NotificationPreferenceSchema)
async def update_notification_preferences(
    preferences_data: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update user notification preferences"""
    
    prefs = await get_user_notification_preferences(current_user.id, db)
    if not prefs:
        # Create new preferences
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)
    
    # Update fields
    update_data = preferences_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prefs, field, value)
    
    await db.commit()
    await db.refresh(prefs)
    
    return NotificationPreferenceSchema.from_orm(prefs)


# Focus Mode Endpoints
@router.post("/focus-mode/enable", response_model=FocusModeStatus)
async def enable_focus_mode(
    duration_minutes: Optional[int] = Query(None, ge=15, le=480),  # 15 min to 8 hours
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Enable focus mode with optional custom duration"""
    
    prefs = await get_user_notification_preferences(current_user.id, db)
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)
    
    prefs.focus_mode_enabled = True
    
    active_until = None
    if duration_minutes:
        active_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
    
    await db.commit()
    
    return FocusModeStatus(
        enabled=True,
        active_until=active_until,
        custom_duration_minutes=duration_minutes
    )


@router.post("/focus-mode/disable", response_model=FocusModeStatus)
async def disable_focus_mode(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Disable focus mode"""
    
    prefs = await get_user_notification_preferences(current_user.id, db)
    if prefs:
        prefs.focus_mode_enabled = False
        await db.commit()
    
    return FocusModeStatus(enabled=False)


# Focus Blocks Endpoints
@router.get("/focus-blocks", response_model=List[FocusBlockSchema])
async def list_focus_blocks(
    include_past: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """List focus blocks for the current user."""
    stmt = select(FocusBlockModel).where(
        and_(
            FocusBlockModel.user_id == current_user.id,
            FocusBlockModel.organization_id == current_org.id,
        )
    ).order_by(FocusBlockModel.start_time.desc())

    if not include_past:
        stmt = stmt.where(FocusBlockModel.end_time >= func.now())

    result = await db.execute(stmt)
    blocks = result.scalars().all()
    return [FocusBlockSchema.from_orm(b) for b in blocks]


@router.post("/focus-blocks", response_model=FocusBlockSchema, status_code=status.HTTP_201_CREATED)
async def create_focus_block(
    data: FocusBlockCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new focus block for the current user."""
    if data.end_time <= data.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    block = FocusBlockModel(
        user_id=current_user.id,
        organization_id=current_org.id,
        created_by_id=current_user.id,
        start_time=data.start_time,
        end_time=data.end_time,
        timezone=data.timezone,
        reason=data.reason,
    )
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return FocusBlockSchema.from_orm(block)


@router.delete("/focus-blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_focus_block(
    block_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> None:
    """Delete a focus block (only owner can delete)."""
    stmt = select(FocusBlockModel).where(
        and_(
            FocusBlockModel.id == block_id,
            FocusBlockModel.user_id == current_user.id,
            FocusBlockModel.organization_id == current_org.id,
        )
    )
    res = await db.execute(stmt)
    block = res.scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="Focus block not found")

    await db.delete(block)
    await db.commit()
    return None


# Digest Endpoints
@router.get("/digest/daily", response_model=NotificationDigest)
async def get_daily_digest(
    date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$'),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get daily notification digest"""
    
    if date:
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
    else:
        target_date = datetime.utcnow().date()
    
    period_start = datetime.combine(target_date, datetime.min.time())
    period_end = period_start + timedelta(days=1)
    
    return await generate_notification_digest(
        current_user.id, current_org.id, "daily", period_start, period_end, db
    )


@router.get("/insights", response_model=SmartNotificationInsights)
async def get_notification_insights(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get smart insights about notification engagement and patterns"""
    
    return await generate_notification_insights(current_user.id, days, db)


# Auto-capture endpoints for Context Cards
@router.post("/auto-capture/analyze-content")
async def analyze_content_for_auto_capture(
    content: str,
    context_type: str,
    entity_id: str,
    entity_type: str,  # "task", "project", "comment"
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Any:
    """Analyze content for potential auto-capture of decision context"""
    
    # Queue background task for AI analysis
    background_tasks.add_task(
        analyze_and_create_context_cards,
        content, context_type, entity_id, entity_type,
        current_user.id, current_org.id, db
    )
    
    return {"message": "Content analysis queued for auto-capture"}


# Helper functions
async def get_user_notification_preferences(user_id: str, db: AsyncSession) -> Optional[NotificationPreference]:
    """Get user notification preferences"""
    query = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def group_notifications_by_context(notifications: List[Notification]) -> Dict[str, List]:
    """Group notifications by context for better organization"""
    grouped = {
        "urgent": [],
        "projects": {},
        "tasks": {},
        "decisions": [],
        "handoffs": [],
        "mentions": [],
        "other": []
    }
    
    for notification in notifications:
        # Add to urgent if high priority
        if notification.priority in [NotificationPriority.URGENT, NotificationPriority.CRITICAL]:
            grouped["urgent"].append(notification)
        
        # Group by project
        if notification.project_id:
            if notification.project_id not in grouped["projects"]:
                grouped["projects"][notification.project_id] = []
            grouped["projects"][notification.project_id].append(notification)
        
        # Group by task
        elif notification.task_id:
            if notification.task_id not in grouped["tasks"]:
                grouped["tasks"][notification.task_id] = []
            grouped["tasks"][notification.task_id].append(notification)
        
        # Group by type
        elif notification.notification_type in [
            NotificationType.DECISION_LOGGED, 
            NotificationType.DECISION_REVIEW_DUE,
            NotificationType.DECISION_STATUS_CHANGED
        ]:
            grouped["decisions"].append(notification)
        
        elif notification.notification_type in [
            NotificationType.HANDOFF_RECEIVED,
            NotificationType.HANDOFF_REVIEWED, 
            NotificationType.HANDOFF_REMINDER
        ]:
            grouped["handoffs"].append(notification)
        
        elif notification.notification_type == NotificationType.MENTION:
            grouped["mentions"].append(notification)
        
        else:
            grouped["other"].append(notification)
    
    return grouped


async def generate_notification_digest(
    user_id: str, org_id: str, digest_type: str, 
    period_start: datetime, period_end: datetime, db: AsyncSession
) -> NotificationDigest:
    """Generate notification digest for a specific period"""
    
    # Get notifications for the period
    query = select(Notification).where(
        and_(
            Notification.user_id == user_id,
            Notification.organization_id == org_id,
            Notification.created_at >= period_start,
            Notification.created_at < period_end
        )
    ).order_by(desc(Notification.priority), desc(Notification.created_at))
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    # Separate urgent notifications
    urgent_notifications = [
        n for n in notifications 
        if n.priority in [NotificationPriority.URGENT, NotificationPriority.CRITICAL]
    ]
    
    # Group by project for summaries
    project_summaries = {}
    for notification in notifications:
        if notification.project_id:
            if notification.project_id not in project_summaries:
                project_summaries[notification.project_id] = {
                    "total_notifications": 0,
                    "urgent_count": 0,
                    "types": {}
                }
            
            project_summaries[notification.project_id]["total_notifications"] += 1
            
            if notification.priority in [NotificationPriority.URGENT, NotificationPriority.CRITICAL]:
                project_summaries[notification.project_id]["urgent_count"] += 1
            
            type_str = notification.notification_type.value
            if type_str not in project_summaries[notification.project_id]["types"]:
                project_summaries[notification.project_id]["types"][type_str] = 0
            project_summaries[notification.project_id]["types"][type_str] += 1
    
    # Get top actions required
    top_actions = [
        n for n in notifications 
        if n.action_required and not n.action_taken
    ][:5]
    
    return NotificationDigest(
        digest_type=digest_type,
        period_start=period_start,
        period_end=period_end,
        total_notifications=len(notifications),
        urgent_notifications=[NotificationSchema.from_orm(n) for n in urgent_notifications],
        project_summaries=project_summaries,
        top_actions_required=[NotificationSchema.from_orm(n) for n in top_actions],
        knowledge_highlights=[]  # TODO: Add knowledge highlights
    )


async def generate_notification_insights(
    user_id: str, days: int, db: AsyncSession
) -> SmartNotificationInsights:
    """Generate smart insights about user's notification patterns"""
    
    period_start = datetime.utcnow() - timedelta(days=days)
    
    # Get notifications and analytics for the period
    notifications_query = select(Notification).where(
        and_(
            Notification.user_id == user_id,
            Notification.created_at >= period_start
        )
    )
    notifications_result = await db.execute(notifications_query)
    notifications = notifications_result.scalars().all()
    
    analytics_query = select(NotificationAnalytics).where(
        and_(
            NotificationAnalytics.user_id == user_id,
            # Join with notifications to filter by date
        )
    )
    analytics_result = await db.execute(analytics_query)
    analytics = analytics_result.scalars().all()
    
    # Calculate metrics
    total_notifications = len(notifications)
    
    # Engagement rate (notifications that were opened/clicked)
    engaged_count = len([a for a in analytics if a.opened_at or a.clicked_at])
    engagement_rate = engaged_count / total_notifications if total_notifications > 0 else 0
    
    # Average relevance score
    relevance_scores = [n.relevance_score for n in notifications if n.relevance_score]
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.5
    
    # Most and least engaged types
    type_engagement = {}
    for notification in notifications:
        type_str = notification.notification_type.value
        if type_str not in type_engagement:
            type_engagement[type_str] = {"total": 0, "engaged": 0}
        type_engagement[type_str]["total"] += 1
        
        # Check if this notification was engaged with
        for analytics_record in analytics:
            if analytics_record.notification_id == notification.id and (analytics_record.opened_at or analytics_record.clicked_at):
                type_engagement[type_str]["engaged"] += 1
                break
    
    # Sort by engagement rate
    type_rates = []
    for type_str, data in type_engagement.items():
        rate = data["engaged"] / data["total"] if data["total"] > 0 else 0
        type_rates.append((type_str, rate))
    
    type_rates.sort(key=lambda x: x[1], reverse=True)
    most_engaged_types = [t[0] for t in type_rates[:3]]
    least_engaged_types = [t[0] for t in type_rates[-3:]]
    
    # Optimal delivery times (based on when user typically engages)
    engaged_hours = []
    for analytics_record in analytics:
        if analytics_record.opened_at:
            hour = analytics_record.opened_at.hour
            engaged_hours.append(f"{hour:02d}:00")
    
    # Get most common engagement hours
    from collections import Counter
    hour_counts = Counter(engaged_hours)
    optimal_times = [hour for hour, count in hour_counts.most_common(3)]
    
    # Generate recommendations
    recommendations = []
    if engagement_rate < 0.3:
        recommendations.append("Consider reducing notification frequency or improving relevance filtering")
    if avg_relevance < 0.4:
        recommendations.append("Enable AI-powered relevance filtering to reduce noise")
    if len(optimal_times) > 0:
        recommendations.append(f"Consider scheduling digests during your most active hours: {', '.join(optimal_times)}")
    
    return SmartNotificationInsights(
        user_id=user_id,
        period_days=days,
        total_notifications=total_notifications,
        engagement_rate=engagement_rate,
        average_relevance_score=avg_relevance,
        most_engaged_types=most_engaged_types,
        least_engaged_types=least_engaged_types,
        optimal_delivery_times=optimal_times,
        recommendations=recommendations
    )


@router.post("/digests/run", response_model=NotificationDigest)
async def run_digest_now(
    digest_type: str = Query("daily", pattern="^(daily|weekly)$"),
    date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$'),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Generate a digest now for the current user (timezone-aware)."""
    # Resolve user's timezone from preferences (fallback to UTC)
    prefs = await get_user_notification_preferences(current_user.id, db)
    tz = prefs.timezone if prefs and getattr(prefs, "timezone", None) else "UTC"
    tzinfo = None
    try:
        tzinfo = ZoneInfo(tz)
    except Exception:
        tzinfo = ZoneInfo("UTC")

    now_local = datetime.utcnow().astimezone(tzinfo)

    if digest_type == "daily":
        if date:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        else:
            target_date = now_local.date()
        period_start_local = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=tzinfo)
        period_end_local = period_start_local + timedelta(days=1)
    else:  # weekly
        # Start from Monday of target week
        if date:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        else:
            target_date = now_local.date()
        weekday = target_date.weekday()  # 0=Mon
        period_start_local = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=tzinfo) - timedelta(days=weekday)
        period_end_local = period_start_local + timedelta(days=7)

    # Convert to UTC naive for DB comparison consistency
    period_start = period_start_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    period_end = period_end_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    return await generate_notification_digest(
        current_user.id, current_org.id, digest_type, period_start, period_end, db
    )


async def analyze_and_create_context_cards(
    content: str, context_type: str, entity_id: str, entity_type: str,
    user_id: str, org_id: str, db: AsyncSession
):
    """Background task to analyze content and auto-create context cards"""
    
    # TODO: Implement AI analysis for decision indicators
    # This would use NLP to detect:
    # - Decision keywords ("decided", "chosen", "selected", "approved")
    # - Rationale indicators ("because", "due to", "in order to")
    # - Impact indicators ("will result in", "affects", "consequences")
    
    # For now, create a simple keyword-based detection
    decision_keywords = [
        "decided", "decision", "choose", "chosen", "selected", "approved",
        "agreed", "concluded", "determined", "resolved"
    ]
    
    rationale_keywords = [
        "because", "due to", "since", "as", "given that", "considering",
        "in order to", "to achieve", "for the purpose of"
    ]
    
    content_lower = content.lower()
    
    # Check if content contains decision indicators
    has_decision = any(keyword in content_lower for keyword in decision_keywords)
    has_rationale = any(keyword in content_lower for keyword in rationale_keywords)
    
    if has_decision or has_rationale:
        # Calculate confidence score
        confidence = 0.3  # Base confidence
        if has_decision:
            confidence += 0.3
        if has_rationale:
            confidence += 0.2
        if len(content) > 100:  # Longer content is more likely to be substantial
            confidence += 0.2
        
        confidence = min(confidence, 1.0)
        
        # Only auto-create if confidence is reasonable
        if confidence >= 0.5:
            from ....models.context_card import ContextCard
            
            # Create auto-captured context card
            context_card = ContextCard(
                title=f"Auto-captured: {context_type} context",
                content=content,
                decision_rationale=content if has_rationale else "",
                context_type="DECISION" if has_decision else "DISCUSSION",
                priority="MEDIUM",
                project_id=entity_id if entity_type == "project" else None,
                task_id=entity_id if entity_type == "task" else None,
                created_by_id=user_id,
                auto_captured=True,
                capture_source=entity_type,
                trigger_event=f"{entity_type}_content_analysis",
                extraction_keywords=[kw for kw in decision_keywords + rationale_keywords if kw in content_lower],
                decision_indicators=[kw for kw in decision_keywords if kw in content_lower],
                confidence_score=confidence,
                auto_review_needed=True
            )
            
            db.add(context_card)
            await db.commit()
            
            # Create notification about the auto-captured context
            from ....models.notification import Notification, NotificationType, NotificationPriority
            
            await create_notification_for_user(
                db,
                user_id=user_id,
                org_id=org_id,
                title="Auto-captured Decision Context",
                message=f"We detected decision context in your {entity_type} and created a context card for review.",
                notification_type=NotificationType.CONTEXT_CARD_LINKED,
                priority=NotificationPriority.NORMAL,
                context_card_id=context_card.id,
                project_id=context_card.project_id,
                task_id=context_card.task_id,
                relevance_score=confidence,
                context_data={
                    "auto_captured": True,
                    "confidence_score": confidence,
                    "needs_review": True
                },
                action_required=True,
                auto_generated=True,
                source="auto_capture_analysis",
            )
