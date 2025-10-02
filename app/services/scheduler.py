import asyncio
from datetime import datetime, timezone
from sqlalchemy import select, and_
from ..db.tenant_manager import tenant_manager
from ..models.recurring_task import RecurringTaskTemplate
from ..models.task import Task
from ..models.project import Project
from ..models.project_report_schedule import ProjectReportSchedule

async def fetch_all_org_ids_from_master() -> list[str]:
    """Fetch organization IDs from the master DB (best-effort)."""
    from sqlalchemy import select as sa_select
    from ..models.organization import Organization
    session = await tenant_manager.get_master_session()
    try:
        res = await session.execute(sa_select(Organization.id).where(Organization.is_active == True))
        return [row[0] for row in res.all()]
    except Exception:
        return []
    finally:
        await session.close()

async def generate_due_recurring_tasks_for_tenant(org_id: str):
    session = await tenant_manager.get_tenant_session(org_id)
    try:
        now = datetime.now(timezone.utc)
        q = select(RecurringTaskTemplate).where(
            RecurringTaskTemplate.is_active == True,
            RecurringTaskTemplate.is_paused == False,
            RecurringTaskTemplate.next_due_date != None,
            RecurringTaskTemplate.next_due_date <= now
        )
        res = await session.execute(q)
        templates = res.scalars().all()
        for tpl in templates:
            task = Task(
                title=tpl.title,
                description=tpl.description,
                project_id=tpl.project_id,
                priority=tpl.priority,
                task_type=tpl.task_type,
                assignee_id=tpl.default_assignee_id,
                estimated_hours=tpl.estimated_hours,
                story_points=tpl.story_points,
                labels=tpl.labels,
                tags=tpl.tags,
                custom_fields=tpl.custom_fields,
                recurring_template_id=tpl.id,
                is_recurring=True,
                due_date=tpl.next_due_date
            )
            session.add(task)
            tpl.total_generated = (tpl.total_generated or 0) + 1
            tpl.last_generated_date = now
            tpl.next_due_date = tpl.calculate_next_due_date()
            # TODO: create in-app notification for assignee
        await session.commit()
    except Exception:
        await session.rollback()
    finally:
        await session.close()

async def send_scheduled_project_reports_for_tenant(org_id: str):
    session = await tenant_manager.get_tenant_session(org_id)
    try:
        now = datetime.now(timezone.utc)
        dom = now.day
        q = select(ProjectReportSchedule).where(
            ProjectReportSchedule.is_active == True,
            ProjectReportSchedule.day_of_month == dom
        )
        res = await session.execute(q)
        schedules = res.scalars().all()
        for sch in schedules:
            # Build a share link and send email to recipients
            share_link = await ensure_project_share_link(session, sch.project_id)
            await send_project_report_emails(sch.recipients or [], share_link)
            sch.last_sent_at = now
        await session.commit()
    except Exception:
        await session.rollback()
    finally:
        await session.close()

async def ensure_project_share_link(session, project_id: str) -> str:
    """Return a stable public share link for the project."""
    # If you already have share links, return them here; otherwise, construct a path-based link
    # e.g., http://localhost:3000/shared/project/{shareId}
    # For now, return a placeholder path that your frontend handles
    return f"/shared/project/{project_id}"

async def send_project_report_emails(recipients: list[str], share_link: str):
    # Plug into your existing email service here.
    # Best-effort: skip sending if configuration is missing.
    try:
        from ..services.email_service import send_report_email
        for r in recipients:
            try:
                send_report_email(r, share_link)
            except Exception:
                continue
    except Exception:
        pass

async def scheduler_tick():
    org_ids = await fetch_all_org_ids_from_master()
    for org_id in org_ids:
        await generate_due_recurring_tasks_for_tenant(org_id)
        await send_scheduled_project_reports_for_tenant(org_id)

async def scheduler_loop():
    while True:
        try:
            await scheduler_tick()
        except Exception:
            pass
        await asyncio.sleep(60)
