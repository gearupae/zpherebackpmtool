from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, func, desc, select, insert
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from ....models.goal import (
    Goal, GoalChecklist, GoalProgress, GoalReminder, 
    GoalType, GoalStatus, GoalPriority, ReminderInterval,
    goal_members
)
from ....models.user import User
from ....schemas.goal import (
    GoalCreate, GoalUpdate, Goal as GoalSchema, GoalSummary,
    GoalChecklistCreate, GoalChecklistUpdate, GoalChecklist as GoalChecklistSchema,
    GoalProgressCreate, GoalProgress as GoalProgressSchema,
    GoalReminderCreate, GoalReminder as GoalReminderSchema,
    GoalMetrics, BulkGoalUpdate, BulkGoalArchive,
    GoalMemberInfo, GoalMemberAdd, GoalMembersAdd, GoalMemberUpdate
)
from ...deps_tenant import get_current_active_user_master, get_tenant_db

router = APIRouter()

# Helper functions
async def get_goal_or_404(db: AsyncSession, goal_id: str, user: User) -> Goal:
    """Get goal by ID or raise 404 if not found or no access"""
    query = select(Goal).options(
        selectinload(Goal.members),
        selectinload(Goal.checklists),
        selectinload(Goal.progress_logs),
        selectinload(Goal.reminders)
    ).where(
        and_(
            Goal.id == goal_id,
            or_(
                Goal.created_by == user.id,
                Goal.members.any(User.id == user.id),
                Goal.organization_id == user.organization_id
            )
        )
    )
    result = await db.execute(query)
    goal = result.scalars().first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal

async def get_goal_member_roles_map(db: AsyncSession, goal_id: str) -> Dict[str, str]:
    """Return {user_id: role} for members of a goal"""
    result = await db.execute(
        select(goal_members.c.user_id, goal_members.c.role).where(goal_members.c.goal_id == goal_id)
    )
    return {user_id: role for user_id, role in result.all()}

async def fetch_goal_members(db: AsyncSession, goal_id: str) -> List[Dict[str, Any]]:
    """Fetch full member info with roles for a goal"""
    result = await db.execute(
        select(
            User.id,
            User.username,
            User.first_name,
            User.last_name,
            User.email,
            User.avatar_url,
            goal_members.c.role
        )
        .join(goal_members, goal_members.c.user_id == User.id)
        .where(goal_members.c.goal_id == goal_id)
    )
    rows = result.all()
    return [
        {
            'id': r[0],
            'username': r[1],
            'first_name': r[2],
            'last_name': r[3],
            'email': r[4],
            'avatar_url': r[5],
            'role': r[6]
        }
        for r in rows
    ]

async def fetch_goal_member(db: AsyncSession, goal_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single member with role for a goal"""
    result = await db.execute(
        select(
            User.id,
            User.username,
            User.first_name,
            User.last_name,
            User.email,
            User.avatar_url,
            goal_members.c.role
        )
        .join(goal_members, goal_members.c.user_id == User.id)
        .where(and_(goal_members.c.goal_id == goal_id, goal_members.c.user_id == user_id))
    )
    row = result.first()
    if not row:
        return None
    r = row
    return {
        'id': r[0],
        'username': r[1],
        'first_name': r[2],
        'last_name': r[3],
        'email': r[4],
        'avatar_url': r[5],
        'role': r[6]
    }

def assert_can_manage_goal_members(goal: Goal, current_user: User) -> None:
    """Only the goal owner (creator) or an admin can manage members"""
    if goal.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions to manage goal members")

def calculate_goal_metrics(goal: Goal) -> Dict[str, Any]:
    """Calculate additional metrics for a goal"""
    completion_percentage = goal.calculate_completion_percentage()
    probability_of_achievement = goal.get_probability_of_achievement()
    
    now = datetime.now(timezone.utc)
    days_remaining = max(0, (goal.end_date - now).days)
    is_overdue = now > goal.end_date and goal.status not in [GoalStatus.COMPLETED, GoalStatus.CANCELLED]
    
    return {
        'completion_percentage': completion_percentage,
        'probability_of_achievement': probability_of_achievement,
        'days_remaining': days_remaining,
        'is_overdue': is_overdue
    }

def serialize_goal_with_metrics(goal: Goal, include_details: bool = True, member_roles: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Serialize goal with calculated metrics and related data"""
    metrics = calculate_goal_metrics(goal)
    
    goal_data = {
        'id': goal.id,
        'title': goal.title,
        'description': goal.description,
        'start_date': goal.start_date,
        'end_date': goal.end_date,
        'goal_type': goal.goal_type,
        'status': goal.status,
        'priority': goal.priority,
        'target_value': goal.target_value,
        'current_value': goal.current_value,
        'unit': goal.unit,
        'project_id': goal.project_id,
        'auto_update_progress': goal.auto_update_progress,
        'tags': goal.tags or [],
        'metadata': getattr(goal, 'meta', None) or {},
        'created_by': goal.created_by,
        'organization_id': goal.organization_id,
        'is_archived': goal.is_archived,
        'created_at': goal.created_at,
        'updated_at': goal.updated_at,
        **metrics
    }
    
    if include_details:
        goal_data.update({
'members': [
                {
                    'id': member.id,
                    'username': member.username,
                    'first_name': member.first_name,
                    'last_name': member.last_name,
                    'email': member.email,
                    'avatar_url': member.avatar_url,
                    'role': (member_roles.get(member.id, 'member') if member_roles else 'member')
                }
                for member in goal.members
            ],
            'checklists': [
                {
                    'id': checklist.id,
                    'goal_id': checklist.goal_id,
                    'title': checklist.title,
                    'description': checklist.description,
                    'is_completed': checklist.is_completed,
                    'completed_at': checklist.completed_at,
                    'completed_by': checklist.completed_by,
                    'due_date': checklist.due_date,
                    'priority': checklist.priority,
                    'order_index': checklist.order_index,
                    'created_at': checklist.created_at,
                    'updated_at': checklist.updated_at
                }
                for checklist in sorted(goal.checklists, key=lambda x: x.order_index)
            ],
            'recent_progress': [
                {
                    'id': progress.id,
                    'goal_id': progress.goal_id,
                    'previous_value': progress.previous_value,
                    'new_value': progress.new_value,
                    'change_amount': progress.change_amount,
                    'notes': progress.notes,
                    'source': progress.source,
                    'reference_id': progress.reference_id,
                    'created_by': progress.created_by,
                    'created_at': progress.created_at
                }
                for progress in sorted(goal.progress_logs, key=lambda x: x.created_at, reverse=True)[:5]
            ],
            'active_reminders': [
                {
                    'id': reminder.id,
                    'goal_id': reminder.goal_id,
                    'interval': reminder.interval,
                    'custom_interval_days': reminder.custom_interval_days,
                    'is_active': reminder.is_active,
                    'last_sent_at': reminder.last_sent_at,
                    'next_reminder_at': reminder.next_reminder_at,
                    'reminder_message': reminder.reminder_message,
                    'send_email': reminder.send_email,
                    'send_in_app': reminder.send_in_app,
                    'send_to_members': reminder.send_to_members,
                    'created_at': reminder.created_at,
                    'updated_at': reminder.updated_at
                }
                for reminder in goal.reminders if reminder.is_active
            ]
        })
    else:
        # For summary view
        goal_data.update({
            'member_count': len(goal.members),
            'checklist_count': len(goal.checklists),
            'completed_checklist_count': sum(1 for c in goal.checklists if c.is_completed)
        })
    
    return goal_data

# Goal CRUD endpoints
@router.get("/", response_model=List[GoalSummary])
async def get_goals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[List[GoalStatus]] = Query(None),
    goal_type: Optional[List[GoalType]] = Query(None),
    priority: Optional[List[GoalPriority]] = Query(None),
    member_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    overdue_only: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Get paginated list of goals with filtering"""
    query = select(Goal).options(
        selectinload(Goal.members),
        selectinload(Goal.checklists)
    ).where(
        or_(
            Goal.created_by == current_user.id,
            Goal.members.any(User.id == current_user.id),
            Goal.organization_id == current_user.organization_id
        )
    )

    if status:
        query = query.where(Goal.status.in_(status))
    if goal_type:
        query = query.where(Goal.goal_type.in_(goal_type))
    if priority:
        query = query.where(Goal.priority.in_(priority))
    if member_id:
        query = query.where(Goal.members.any(User.id == member_id))
    if project_id:
        query = query.where(Goal.project_id == project_id)
    if tags:
        for tag in tags:
            query = query.where(Goal.tags.contains([tag]))
    if overdue_only:
        now = datetime.now(timezone.utc)
        query = query.where(
            and_(
                Goal.end_date < now,
                Goal.status.notin_([GoalStatus.COMPLETED, GoalStatus.CANCELLED])
            )
        )
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Goal.title.ilike(search_term),
                Goal.description.ilike(search_term)
            )
        )

    query = query.where(Goal.is_archived == False)
    query = query.order_by(Goal.priority.desc(), Goal.end_date.asc()).offset(skip).limit(limit)

    result = await db.execute(query)
    goals = result.scalars().all()
    return [serialize_goal_with_metrics(goal, include_details=False) for goal in goals]

@router.post("/", response_model=GoalSchema)
async def create_goal(
    goal_data: GoalCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Create a new goal"""
    
    # Create the goal
    goal = Goal(
        title=goal_data.title,
        description=goal_data.description,
        start_date=goal_data.start_date,
        end_date=goal_data.end_date,
        goal_type=goal_data.goal_type,
        priority=goal_data.priority,
        target_value=goal_data.target_value or 0,
        unit=goal_data.unit,
        project_id=goal_data.project_id,
        auto_update_progress=goal_data.auto_update_progress,
        tags=goal_data.tags,
        meta=goal_data.metadata,
        created_by=current_user.id,
        organization_id=current_user.organization_id
    )
    
    db.add(goal)
    await db.flush()  # Get the goal ID
    
    # Add members via association table to avoid relationship lazy-loads on AsyncSession
    member_ids = set(goal_data.member_ids or [])
    member_ids.add(current_user.id)
    if member_ids:
        await db.execute(
            insert(goal_members),
            [
                {"goal_id": goal.id, "user_id": mid, "role": ("owner" if mid == current_user.id else "member")}
                for mid in member_ids
            ]
        )
    
    # Create checklist items
    for i, checklist_item in enumerate(goal_data.checklist_items or []):
        checklist = GoalChecklist(
            goal_id=goal.id,
            title=checklist_item.get('title', ''),
            description=checklist_item.get('description'),
            due_date=checklist_item.get('due_date'),
            priority=GoalPriority(checklist_item.get('priority', 'medium')),
            order_index=i
        )
        db.add(checklist)
    
    # Create reminder if specified
    if goal_data.reminder_settings:
        reminder = GoalReminder(
            goal_id=goal.id,
            interval=ReminderInterval(goal_data.reminder_settings.get('interval', 'weekly')),
            custom_interval_days=goal_data.reminder_settings.get('custom_interval_days'),
            reminder_message=goal_data.reminder_settings.get('message'),
            send_email=goal_data.reminder_settings.get('send_email', True),
            send_in_app=goal_data.reminder_settings.get('send_in_app', True),
            send_to_members=goal_data.reminder_settings.get('send_to_members', True)
        )
        reminder.next_reminder_at = reminder.calculate_next_reminder()
        db.add(reminder)
    
    await db.commit()
    await db.refresh(goal)
    
    # Load related data
    result = await db.execute(
        select(Goal).options(
            selectinload(Goal.members),
            selectinload(Goal.checklists),
            selectinload(Goal.progress_logs),
            selectinload(Goal.reminders)
        ).where(Goal.id == goal.id)
    )
    goal_loaded = result.scalars().first()
    
    roles_map = await get_goal_member_roles_map(db, goal_loaded.id)
    return serialize_goal_with_metrics(goal_loaded, member_roles=roles_map)

@router.get("/{goal_id}", response_model=GoalSchema)
async def get_goal(
    goal_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Get a specific goal by ID"""
    goal = await get_goal_or_404(db, goal_id, current_user)
    roles_map = await get_goal_member_roles_map(db, goal.id)
    return serialize_goal_with_metrics(goal, member_roles=roles_map)

@router.put("/{goal_id}", response_model=GoalSchema)
async def update_goal(
    goal_id: str,
    goal_update: GoalUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Update a goal"""
    goal = await get_goal_or_404(db, goal_id, current_user)
    
    # Update fields
    update_data = goal_update.dict(exclude_unset=True)
    # Map reserved 'metadata' field to model's 'meta'
    if 'metadata' in update_data:
        goal.meta = update_data.pop('metadata')

    # Handle current_value separately to record a progress log
    prev_value = goal.current_value
    if 'current_value' in update_data:
        new_value = update_data.pop('current_value')
        if new_value is not None and new_value != prev_value:
            progress = GoalProgress(
                goal_id=goal.id,
                previous_value=prev_value,
                new_value=new_value,
                change_amount=new_value - (prev_value or 0),
                notes="Manual update",
                source="manual",
                created_by=current_user.id
            )
            db.add(progress)
        goal.current_value = new_value

    # Apply remaining simple field updates
    for field, value in update_data.items():
        setattr(goal, field, value)

    # Recalculate completion
    goal.completion_percentage = goal.calculate_completion_percentage()
    
    # Update status based on completion
    if goal.completion_percentage >= 100 and goal.status != GoalStatus.COMPLETED:
        goal.status = GoalStatus.COMPLETED
    elif goal.completion_percentage > 0 and goal.status == GoalStatus.NOT_STARTED:
        goal.status = GoalStatus.IN_PROGRESS
    
    await db.commit()
    await db.refresh(goal)
    
    roles_map = await get_goal_member_roles_map(db, goal.id)
    return serialize_goal_with_metrics(goal, member_roles=roles_map)

@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Delete a goal (only creator or admin can delete)"""
    goal = await get_goal_or_404(db, goal_id, current_user)
    
    if goal.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    await db.delete(goal)
    await db.commit()
    return {"message": "Goal deleted successfully"}

# Goal member endpoints
@router.get("/{goal_id}/members", response_model=List[GoalMemberInfo])
async def get_goal_members(
    goal_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """List members of a goal with roles"""
    await get_goal_or_404(db, goal_id, current_user)
    return await fetch_goal_members(db, goal_id)

@router.post("/{goal_id}/members", response_model=List[GoalMemberInfo])
async def add_goal_members(
    goal_id: str,
    members_data: GoalMembersAdd,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Add one or more members to a goal"""
    goal = await get_goal_or_404(db, goal_id, current_user)
    assert_can_manage_goal_members(goal, current_user)

    # Existing members
    result = await db.execute(select(goal_members.c.user_id).where(goal_members.c.goal_id == goal_id))
    existing_user_ids = {row[0] for row in result.all()}

    # Validate users exist in this tenant DB
    requested_ids = {m.user_id for m in (members_data.members or []) if m.user_id not in existing_user_ids}
    if requested_ids:
        user_res = await db.execute(select(User.id).where(User.id.in_(requested_ids)))
        found_user_ids = {row[0] for row in user_res.all()}
        missing = requested_ids - found_user_ids
        if missing:
            raise HTTPException(status_code=404, detail=f"User(s) not found: {', '.join(missing)}")

    to_insert = []
    for m in members_data.members or []:
        if m.user_id not in existing_user_ids:
            to_insert.append({"goal_id": goal_id, "user_id": m.user_id, "role": m.role or "member"})

    if to_insert:
        await db.execute(insert(goal_members), to_insert)
        await db.commit()

    return await fetch_goal_members(db, goal_id)

@router.patch("/{goal_id}/members/{user_id}", response_model=GoalMemberInfo)
async def update_goal_member_role(
    goal_id: str,
    user_id: str,
    update: GoalMemberUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Update a member's role in a goal"""
    goal = await get_goal_or_404(db, goal_id, current_user)
    assert_can_manage_goal_members(goal, current_user)

    # Ensure the membership exists
    result = await db.execute(
        select(goal_members).where(and_(goal_members.c.goal_id == goal_id, goal_members.c.user_id == user_id))
    )
    if not result.first():
        raise HTTPException(status_code=404, detail="Member not found for this goal")

    await db.execute(
        goal_members.update().where(and_(goal_members.c.goal_id == goal_id, goal_members.c.user_id == user_id)).values(role=update.role)
    )
    await db.commit()

    member = await fetch_goal_member(db, goal_id, user_id)
    if not member:
        # Should not happen after successful update
        raise HTTPException(status_code=404, detail="Member not found after update")
    return member

@router.delete("/{goal_id}/members/{user_id}")
async def remove_goal_member(
    goal_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Remove a member from a goal"""
    goal = await get_goal_or_404(db, goal_id, current_user)
    assert_can_manage_goal_members(goal, current_user)

    if user_id == goal.created_by:
        raise HTTPException(status_code=400, detail="Cannot remove the goal owner")

    result = await db.execute(
        select(goal_members).where(and_(goal_members.c.goal_id == goal_id, goal_members.c.user_id == user_id))
    )
    assoc = result.first()
    if not assoc:
        raise HTTPException(status_code=404, detail="Member not found for this goal")

    await db.execute(
        goal_members.delete().where(and_(goal_members.c.goal_id == goal_id, goal_members.c.user_id == user_id))
    )
    await db.commit()

    return {"message": "Member removed from goal"}

# Goal checklist endpoints
@router.post("/{goal_id}/checklist", response_model=GoalChecklistSchema)
async def add_checklist_item(
    goal_id: str,
    checklist_data: GoalChecklistCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Add a checklist item to a goal"""
    await get_goal_or_404(db, goal_id, current_user)
    
    # Get the next order index
    result = await db.execute(select(func.max(GoalChecklist.order_index)).where(GoalChecklist.goal_id == goal_id))
    max_order = result.scalar() or 0
    
    checklist = GoalChecklist(
        goal_id=goal_id,
        title=checklist_data.title,
        description=checklist_data.description,
        due_date=checklist_data.due_date,
        priority=checklist_data.priority,
        order_index=max_order + 1
    )
    
    db.add(checklist)
    await db.commit()
    await db.refresh(checklist)
    
    return checklist

@router.put("/checklist/{checklist_id}", response_model=GoalChecklistSchema)
async def update_checklist_item(
    checklist_id: str,
    checklist_update: GoalChecklistUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Update a checklist item"""
    result = await db.execute(select(GoalChecklist).where(GoalChecklist.id == checklist_id))
    checklist = result.scalars().first()
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    
    # Check if user has access to the goal
    goal = await get_goal_or_404(db, checklist.goal_id, current_user)
    
    # Update fields
    update_data = checklist_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(checklist, field, value)
    
    # If marking as completed, set completion details
    if 'is_completed' in update_data and update_data['is_completed']:
        checklist.completed_at = datetime.now(timezone.utc)
        checklist.completed_by = current_user.id
    elif 'is_completed' in update_data and not update_data['is_completed']:
        checklist.completed_at = None
        checklist.completed_by = None
    
    await db.commit()
    await db.refresh(checklist)
    
    # Update goal completion percentage
    goal.completion_percentage = goal.calculate_completion_percentage()
    await db.commit()
    
    return checklist

@router.delete("/checklist/{checklist_id}")
async def delete_checklist_item(
    checklist_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Delete a checklist item"""
    result = await db.execute(select(GoalChecklist).where(GoalChecklist.id == checklist_id))
    checklist = result.scalars().first()
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    
    # Check if user has access to the goal
    goal = await get_goal_or_404(db, checklist.goal_id, current_user)
    
    await db.delete(checklist)
    await db.commit()
    
    # Update goal completion percentage
    goal.completion_percentage = goal.calculate_completion_percentage()
    await db.commit()
    
    return {"message": "Checklist item deleted successfully"}

# Goal progress endpoints
@router.post("/{goal_id}/progress", response_model=GoalProgressSchema)
async def add_progress_update(
    goal_id: str,
    progress_data: GoalProgressCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Add a progress update to a goal"""
    goal = await get_goal_or_404(db, goal_id, current_user)
    
    progress = GoalProgress(
        goal_id=goal_id,
        previous_value=goal.current_value,
        new_value=progress_data.new_value,
        change_amount=progress_data.new_value - goal.current_value,
        notes=progress_data.notes,
        source=progress_data.source,
        reference_id=progress_data.reference_id,
        created_by=current_user.id
    )
    
    # Update goal's current value
    goal.current_value = progress_data.new_value
    goal.completion_percentage = goal.calculate_completion_percentage()
    
    # Update status based on completion
    if goal.completion_percentage >= 100 and goal.status != GoalStatus.COMPLETED:
        goal.status = GoalStatus.COMPLETED
    elif goal.completion_percentage > 0 and goal.status == GoalStatus.NOT_STARTED:
        goal.status = GoalStatus.IN_PROGRESS
    
    db.add(progress)
    await db.commit()
    await db.refresh(progress)
    
    return progress

@router.get("/{goal_id}/progress", response_model=List[GoalProgressSchema])
async def get_goal_progress(
    goal_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Get progress history for a goal"""
    await get_goal_or_404(db, goal_id, current_user)
    
    result = await db.execute(
        select(GoalProgress).where(GoalProgress.goal_id == goal_id).order_by(desc(GoalProgress.created_at)).limit(limit)
    )
    return result.scalars().all()

# Analytics and metrics endpoints
@router.get("/analytics/metrics", response_model=GoalMetrics)
async def get_goal_metrics(
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Get goal analytics and metrics"""
    
# Load all accessible, non-archived goals
    # Preload relationships to avoid async lazy-loads (which cause greenlet errors)
    result = await db.execute(
        select(Goal)
        .options(
            selectinload(Goal.members),
            selectinload(Goal.checklists)
        )
        .where(
            and_(
                or_(
                    Goal.created_by == current_user.id,
                    Goal.members.any(User.id == current_user.id),
                    Goal.organization_id == current_user.organization_id
                ),
                Goal.is_archived == False
            )
        )
    )
    goals = result.scalars().all()
    
    total_goals = len(goals)
    active_goals = sum(1 for g in goals if g.status in [GoalStatus.IN_PROGRESS, GoalStatus.NOT_STARTED])
    completed_goals = sum(1 for g in goals if g.status == GoalStatus.COMPLETED)
    
    # Overdue goals
    now = datetime.now(timezone.utc)
    overdue_goals = sum(1 for g in goals if (g.end_date < now and g.status not in [GoalStatus.COMPLETED, GoalStatus.CANCELLED]))
    
    # Average completion rate
    completion_rates = [g.calculate_completion_percentage() for g in goals]
    average_completion_rate = sum(completion_rates) / len(completion_rates) if completion_rates else 0
    
    # Goals by type
    goals_by_type = {gt.value: 0 for gt in GoalType}
    for g in goals:
        goals_by_type[g.goal_type.value] = goals_by_type.get(g.goal_type.value, 0) + 1
    
    # Goals by priority
    goals_by_priority = {gp.value: 0 for gp in GoalPriority}
    for g in goals:
        goals_by_priority[g.priority.value] = goals_by_priority.get(g.priority.value, 0) + 1
    
    # Upcoming deadlines (next 30 days)
    upcoming_deadlines = [
        serialize_goal_with_metrics(g, include_details=False)
        for g in sorted(
            [x for x in goals if (x.end_date >= now and x.end_date <= now + timedelta(days=30) and x.status not in [GoalStatus.COMPLETED, GoalStatus.CANCELLED])],
            key=lambda x: x.end_date
        )[:10]
    ]
    
    # High probability goals (>75% probability)
    high_prob_goals = []
    low_prob_goals = []
    
    for g in goals:
        if g.status in [GoalStatus.IN_PROGRESS, GoalStatus.NOT_STARTED]:
            probability = g.get_probability_of_achievement()
            if probability > 75:
                high_prob_goals.append(serialize_goal_with_metrics(g, include_details=False))
            elif probability < 25:
                low_prob_goals.append(serialize_goal_with_metrics(g, include_details=False))
    
    return GoalMetrics(
        total_goals=total_goals,
        active_goals=active_goals,
        completed_goals=completed_goals,
        overdue_goals=overdue_goals,
        average_completion_rate=average_completion_rate,
        goals_by_type=goals_by_type,
        goals_by_priority=goals_by_priority,
        upcoming_deadlines=upcoming_deadlines[:5],
        high_probability_goals=high_prob_goals[:5],
        low_probability_goals=low_prob_goals[:5]
    )

# Bulk operations
@router.put("/bulk/update")
async def bulk_update_goals(
    bulk_update: BulkGoalUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Bulk update multiple goals"""
    result = await db.execute(select(Goal).where(
        and_(
            Goal.id.in_(bulk_update.goal_ids),
            or_(
                Goal.created_by == current_user.id,
                Goal.members.any(User.id == current_user.id),
                Goal.organization_id == current_user.organization_id
            )
        )
    ))
    goals = result.scalars().all()
    
    if not goals:
        raise HTTPException(status_code=404, detail="No accessible goals found")
    
    update_data = bulk_update.updates.dict(exclude_unset=True)
    updated_count = 0
    
    for goal in goals:
        for field, value in update_data.items():
            setattr(goal, field, value)
        updated_count += 1
    
    await db.commit()
    
    return {"message": f"Updated {updated_count} goals successfully"}

@router.put("/bulk/archive")
async def bulk_archive_goals(
    bulk_archive: BulkGoalArchive,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Bulk archive/unarchive multiple goals"""
    result = await db.execute(select(Goal).where(
        and_(
            Goal.id.in_(bulk_archive.goal_ids),
            or_(
                Goal.created_by == current_user.id,
                Goal.members.any(User.id == current_user.id),
                Goal.organization_id == current_user.organization_id
            )
        )
    ))
    goals = result.scalars().all()
    
    if not goals:
        raise HTTPException(status_code=404, detail="No accessible goals found")
    
    updated_count = 0
    for goal in goals:
        goal.is_archived = bulk_archive.archive
        updated_count += 1
    
    await db.commit()
    
    action = "archived" if bulk_archive.archive else "unarchived"
    return {"message": f"{action.capitalize()} {updated_count} goals successfully"}

# Goal reminders
@router.post("/{goal_id}/reminders", response_model=GoalReminderSchema)
async def create_goal_reminder(
    goal_id: str,
    reminder_data: GoalReminderCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Create a reminder for a goal"""
    await get_goal_or_404(db, goal_id, current_user)
    
    reminder = GoalReminder(
        goal_id=goal_id,
        interval=reminder_data.interval,
        custom_interval_days=reminder_data.custom_interval_days,
        is_active=reminder_data.is_active,
        reminder_message=reminder_data.reminder_message,
        send_email=reminder_data.send_email,
        send_in_app=reminder_data.send_in_app,
        send_to_members=reminder_data.send_to_members
    )
    
    reminder.next_reminder_at = reminder.calculate_next_reminder()
    
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    
    return reminder

@router.get("/{goal_id}/reminders", response_model=List[GoalReminderSchema])
async def get_goal_reminders(
    goal_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user_master)
):
    """Get all reminders for a goal"""
    await get_goal_or_404(db, goal_id, current_user)
    
    result = await db.execute(select(GoalReminder).where(GoalReminder.goal_id == goal_id))
    reminders = result.scalars().all()
    return reminders
