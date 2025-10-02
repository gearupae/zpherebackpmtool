from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from datetime import datetime, timedelta, timezone

from ...deps import get_current_active_user
from ...deps_tenant import get_tenant_db
from ....models.user import User
from ....models.task import Task
from ....models.project import Project
from ....models.goal import Goal
from ....models.task_assignee import TaskAssignee
from pydantic import BaseModel, field_validator
from fastapi import Body

router = APIRouter()


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.isoformat()


class AvailabilityRequest(BaseModel):
    user_ids: list[str]
    start: str
    end: str
    exclude_task_id: str | None = None

    @field_validator('user_ids')
    @classmethod
    def non_empty_users(cls, v):
        if not v:
            raise ValueError('user_ids must not be empty')
        return v


@router.post("/availability")
async def check_availability(
    payload: AvailabilityRequest = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict]:
    """Check if given users are available between start and end.
    Returns per-user conflicts based on overlapping tasks (primary or additional assignees).
    """
    try:
        start_dt = datetime.fromisoformat(payload.start)
        end_dt = datetime.fromisoformat(payload.end)
    except Exception:
        raise ValueError("Invalid start/end format; must be ISO datetime")

    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt

    results: dict[str, dict] = {uid: {"user_id": uid, "available": True, "conflicts": []} for uid in payload.user_ids}

    # Query overlapping tasks for the organization involving any of these users
    # Overlap condition: (t.start_date <= end AND t.due_date >= start) with null handling
    cond_overlap = or_(
        and_(Task.start_date != None, Task.start_date <= end_dt),
        and_(Task.due_date != None, Task.due_date >= start_dt)
    )

    stmt = (
        select(Task, TaskAssignee)
        .join(Project, Project.id == Task.project_id)
        .outerjoin(TaskAssignee, TaskAssignee.task_id == Task.id)
        .where(
            and_(
                Project.organization_id == current_user.organization_id,
                cond_overlap,
                or_(
                    Task.assignee_id.in_(payload.user_ids),
                    TaskAssignee.user_id.in_(payload.user_ids)
                ),
                Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED])
            )
        )
    )
    if payload.exclude_task_id:
        stmt = stmt.where(Task.id != payload.exclude_task_id)

    res = await db.execute(stmt)
    rows = res.all()
    for t, ta in rows:
        # Determine which users are conflicted for this row
        user_hits = set()
        if t.assignee_id in payload.user_ids:
            user_hits.add(t.assignee_id)
        if ta and ta.user_id in payload.user_ids:
            user_hits.add(ta.user_id)
        start_v = t.start_date or t.due_date
        end_v = t.due_date or t.start_date or start_v
        for uid in user_hits:
            results[uid]["available"] = False
            results[uid]["conflicts"].append({
                "task_id": t.id,
                "title": t.title,
                "start": _iso(start_v),
                "end": _iso(end_v),
                "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
                "primary": (t.assignee_id == uid)
            })

    return list(results.values())


@router.get("/events")
async def get_calendar_events(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    start: Optional[str] = Query(None, description="ISO start datetime filter"),
    end: Optional[str] = Query(None, description="ISO end datetime filter"),
) -> List[dict]:
    """Return aggregated calendar events for the tenant: tasks, projects, goals.
    Each event includes id, entity_type, title, start, end, status/priority, and a client URL path.
    """
    # Determine range
    try:
        start_dt = datetime.fromisoformat(start) if start else datetime.now(timezone.utc) - timedelta(days=30)
    except Exception:
        start_dt = datetime.now(timezone.utc) - timedelta(days=30)
    try:
        end_dt = datetime.fromisoformat(end) if end else datetime.now(timezone.utc) + timedelta(days=90)
    except Exception:
        end_dt = datetime.now(timezone.utc) + timedelta(days=90)

    events: List[dict] = []

    # Projects (filter by org in tenant DB; also date overlap with range)
    proj_stmt = select(Project).where(
        and_(
            # In tenant DB, projects belong to single org, but keep check for safety
            Project.organization_id == current_user.organization_id,
            or_(
                and_(Project.start_date != None, Project.start_date <= end_dt),
                and_(Project.due_date != None, Project.due_date >= start_dt),
            )
        )
    )
    proj_res = await db.execute(proj_stmt)
    for p in proj_res.scalars().all():
        start_v = p.start_date or p.due_date
        end_v = p.due_date or p.start_date or start_v
        if not start_v:
            continue
        events.append({
            "id": p.id,
            "entity_type": "project",
            "title": p.name,
            "start": _iso(start_v),
            "end": _iso(end_v),
            "status": (p.status.value if hasattr(p.status, 'value') else str(p.status)) if p.status else None,
            "priority": (p.priority.value if hasattr(p.priority, 'value') else str(p.priority)) if p.priority else None,
            "url": f"/projects/{p.id}",
        })

    # Tasks: join via project to constrain by org
    task_stmt = select(Task).join(Project, Project.id == Task.project_id).where(
        and_(
            Project.organization_id == current_user.organization_id,
            or_(
                and_(Task.start_date != None, Task.start_date <= end_dt),
                and_(Task.due_date != None, Task.due_date >= start_dt),
            )
        )
    )
    task_res = await db.execute(task_stmt)
    for t in task_res.scalars().all():
        start_v = t.start_date or t.due_date
        end_v = t.due_date or t.start_date or start_v
        if not start_v:
            continue
        events.append({
            "id": t.id,
            "entity_type": "task",
            "title": t.title,
            "start": _iso(start_v),
            "end": _iso(end_v),
            "status": (t.status.value if hasattr(t.status, 'value') else str(t.status)) if t.status else None,
            "priority": (t.priority.value if hasattr(t.priority, 'value') else str(t.priority)) if t.priority else None,
            "url": f"/tasks/{t.id}",
        })

    # Goals
    goal_stmt = select(Goal).where(
        and_(
            Goal.organization_id == current_user.organization_id,
            or_(
                and_(Goal.start_date != None, Goal.start_date <= end_dt),
                and_(Goal.end_date != None, Goal.end_date >= start_dt),
            )
        )
    )
    goal_res = await db.execute(goal_stmt)
    for g in goal_res.scalars().all():
        start_v = g.start_date
        end_v = g.end_date or g.start_date
        if not start_v:
            continue
        events.append({
            "id": g.id,
            "entity_type": "goal",
            "title": g.title,
            "start": _iso(start_v),
            "end": _iso(end_v),
            "status": (g.status.value if hasattr(g.status, 'value') else str(g.status)) if g.status else None,
            "priority": (g.priority.value if hasattr(g.priority, 'value') else str(g.priority)) if g.priority else None,
            "url": f"/goals/{g.id}",
        })

    # Optionally sort by start
    events.sort(key=lambda e: e.get("start") or "")
    return events
