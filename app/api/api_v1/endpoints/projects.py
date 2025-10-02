from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ....db.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_
from sqlalchemy.orm import selectinload
from ....models.user import User
from ....models.project import Project as ProjectModel, ProjectMember, ProjectMemberRole
from ....models.task import Task, TaskStatus
from ....models.project_invoice import ProjectInvoice as InvoiceModel
from ....models.organization import Organization
from ....services.pdf_service import PDFService
from fastapi.responses import StreamingResponse
import io
from ....schemas.project import Project, ProjectCreate, ProjectUpdate, ProjectMemberIn
from ...deps_tenant import get_current_active_user_master
from ....api.deps_tenant import get_master_db as get_db
from ...deps_tenant import get_tenant_db
from ....db.tenant_manager import tenant_manager
import uuid
import re
from datetime import datetime, date
from .websockets import send_project_update as ws_send_project_update

router = APIRouter()

@router.get("/{project_id}/report-schedule")
async def get_report_schedule(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    from ....models.project_report_schedule import ProjectReportSchedule
    from sqlalchemy import select
    res = await db.execute(select(ProjectReportSchedule).where(ProjectReportSchedule.project_id == project_id))
    sch = res.scalar_one_or_none()
    if not sch:
        return {"project_id": project_id, "is_active": False, "day_of_month": None, "recipients": []}
    return {
        "project_id": project_id,
        "is_active": sch.is_active,
        "day_of_month": sch.day_of_month,
        "recipients": sch.recipients or [],
        "last_sent_at": sch.last_sent_at
    }

@router.put("/{project_id}/report-schedule")
async def upsert_report_schedule(
    project_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db)
):
    from ....models.project_report_schedule import ProjectReportSchedule
    from sqlalchemy import select
    res = await db.execute(select(ProjectReportSchedule).where(ProjectReportSchedule.project_id == project_id))
    sch = res.scalar_one_or_none()
    if not sch:
        sch = ProjectReportSchedule(project_id=project_id)
        db.add(sch)
    sch.day_of_month = int(payload.get("day_of_month") or 1)
    sch.recipients = payload.get("recipients") or []
    sch.is_active = bool(payload.get("is_active", True))
    await db.commit()
    await db.refresh(sch)
    return {"message": "Saved", "project_id": project_id}

@router.get("/shared/{share_id}/report")
async def get_shared_project_report(
    share_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Public project report payload (simplified). No auth required here by design.
    share_id can map to a project ID for now; replace with proper share token if available.
    """
    try:
        # For now, interpret share_id as project_id directly
        from ....models.project import Project
        from ....models.task import Task
        from sqlalchemy import select, and_
        proj_res = await db.execute(select(Project).where(Project.id == share_id))
        project = proj_res.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        # Completed tasks in the last 31 days
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        past = now - timedelta(days=31)
        tasks_res = await db.execute(select(Task).where(and_(Task.project_id == project.id, Task.status == 'completed')))
        tasks = tasks_res.scalars().all()
        return {
            "project": {
                "id": project.id,
                "name": project.name,
                "description": project.description,
            },
            "period": {
                "from": past.isoformat(),
                "to": now.isoformat(),
            },
            "completed_tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "completed_date": getattr(t, 'completed_date', None),
                    "attachments": [],
                    "documents": [],
                    "comments": [],
                } for t in tasks
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build report: {str(e)}")


@router.get("/{project_id}/report/pdf")
async def download_project_report_pdf(
    project_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> StreamingResponse:
    """Generate and download a branded project report PDF for the current tenant."""
    # Load project with owner
    result = await db.execute(
        select(ProjectModel)
        .options(selectinload(ProjectModel.owner))
        .where(
            (ProjectModel.id == project_id)
            & (ProjectModel.organization_id == current_user.organization_id)
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Task summary by status
    task_counts_res = await db.execute(
        select(Task.status, func.count())
        .where(Task.project_id == project.id)
        .group_by(Task.status)
    )
    tasks_summary = { (status.value if hasattr(status, 'value') else str(status)): count for status, count in task_counts_res.fetchall() }

    # Invoice totals for project
    inv_totals_res = await db.execute(
        select(
            func.coalesce(func.sum(InvoiceModel.total_amount), 0),
            func.coalesce(func.sum(InvoiceModel.amount_paid), 0),
            func.coalesce(func.sum(InvoiceModel.balance_due), 0),
        ).where(
            (InvoiceModel.project_id == project.id) & (InvoiceModel.organization_id == current_user.organization_id)
        )
    )
    total_amount, amount_paid, balance_due = inv_totals_res.first()

    report = {
        "project": {
            "name": project.name,
            "status": project.status.value if getattr(project, 'status', None) else "",
            "owner": f"{getattr(project.owner, 'first_name', '')} {getattr(project.owner, 'last_name', '')}".strip(),
        },
        "tasks": tasks_summary,
        "invoices": {
            "Invoiced": (total_amount or 0) / 100,
            "Paid": (amount_paid or 0) / 100,
            "Outstanding": (balance_due or 0) / 100,
        },
        "generated_at": datetime.utcnow().isoformat(),
    }

    # Organization branding
    org_res = await db.execute(select(Organization).where(Organization.id == current_user.organization_id))
    org_obj = org_res.scalar_one_or_none()
    org = {"name": org_obj.name, "settings": org_obj.settings or {}, "branding": org_obj.branding or {}} if org_obj else {}

    pdf_service = PDFService()
    pdf_buffer = pdf_service.generate_project_report_pdf(report, org=org)

    filename = f"project_report_{project.slug if getattr(project, 'slug', None) else project.id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_buffer.read()),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def create_slug(name: str) -> str:
    """Create a URL-friendly slug from project name"""
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


@router.get("/", response_model=List[Project])
async def get_projects(
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
    q: Optional[str] = None,
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
) -> Any:
    """Get all projects for current organization"""
    # Query projects where user is a member or owner
    query = (
        select(ProjectModel)
        .where(
            (ProjectModel.organization_id == current_user.organization_id)
            & (ProjectModel.is_archived == False)
        )
        .order_by(ProjectModel.updated_at.desc())
        .options(
            selectinload(ProjectModel.members).selectinload(ProjectMember.user)
        )
    )

    # Optional search filter (name, slug, description)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                ProjectModel.name.ilike(pattern),
                ProjectModel.slug.ilike(pattern),
                ProjectModel.description.ilike(pattern)
            )
        )

    # Optional date filters (match if either start_date or due_date is within range)
    if from_date:
        query = query.where(
            or_(
                func.date(ProjectModel.start_date) >= from_date,
                func.date(ProjectModel.due_date) >= from_date,
            )
        )
    if to_date:
        query = query.where(
            or_(
                func.date(ProjectModel.start_date) <= to_date,
                func.date(ProjectModel.due_date) <= to_date,
            )
        )
    
    result = await db.execute(query)
    projects = result.scalars().unique().all()
    
    return projects


@router.post("/", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new project"""
    # Generate slug if not provided
    if not project_data.slug:
        project_data.slug = create_slug(project_data.name)
    
    # Check if slug already exists in organization
    existing_query = select(ProjectModel).where(
        (ProjectModel.slug == project_data.slug) &
        (ProjectModel.organization_id == current_user.organization_id)
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project with this slug already exists"
        )
    
    # Create project
    base_fields = project_data.model_dump(exclude={"members"})
    project = ProjectModel(
        id=str(uuid.uuid4()),
        organization_id=current_user.organization_id,
        owner_id=current_user.id,
        **base_fields
    )
    
    db.add(project)
    await db.flush()
    
    # Add creator as project owner (always)
    owner_member = ProjectMember(
        id=str(uuid.uuid4()),
        project_id=project.id,
        user_id=current_user.id,
        role=ProjectMemberRole.OWNER,
        can_edit_project=True,
        can_create_tasks=True,
        can_assign_tasks=True,
        can_delete_tasks=True,
    )
    db.add(owner_member)
    
    # Add any additional members provided
    if project_data.members:
        for m in project_data.members:
            if m.user_id == current_user.id:
                # Skip duplicate; ensure at least owner record exists
                continue
            # Ensure the member user exists in the tenant DB (clone from master if needed)
            t_res = await db.execute(select(User).where(User.id == m.user_id))
            t_user = t_res.scalar_one_or_none()
            if not t_user:
                master_session = await tenant_manager.get_master_session()
                try:
                    m_res = await master_session.execute(select(User).where(User.id == m.user_id))
                    m_user = m_res.scalar_one_or_none()
                    if not m_user:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Member user not found: {m.user_id}")
                    clone_user = User(
                        id=m_user.id,
                        email=m_user.email,
                        username=m_user.username,
                        first_name=m_user.first_name,
                        last_name=m_user.last_name,
                        hashed_password=m_user.hashed_password,
                        organization_id=m_user.organization_id,
                        role=m_user.role,
                        status=m_user.status,
                        is_active=m_user.is_active,
                        is_verified=m_user.is_verified,
                        timezone=m_user.timezone,
                        phone=m_user.phone,
                        bio=m_user.bio,
                        address=getattr(m_user, "address", None),
                        preferences=m_user.preferences,
                        notification_settings=m_user.notification_settings,
                        last_login=m_user.last_login,
                        password_changed_at=m_user.password_changed_at,
                        avatar_url=getattr(m_user, "avatar_url", None),
                    )
                    db.add(clone_user)
                    await db.flush()
                finally:
                    await master_session.close()
            db.add(
                ProjectMember(
                    id=str(uuid.uuid4()),
                    project_id=project.id,
                    user_id=m.user_id,
                    role=m.role or ProjectMemberRole.MEMBER,
                    can_edit_project=bool(m.can_edit_project),
                    can_create_tasks=bool(m.can_create_tasks if m.can_create_tasks is not None else True),
                    can_assign_tasks=bool(m.can_assign_tasks),
                    can_delete_tasks=bool(m.can_delete_tasks),
                )
            )
    
    await db.commit()
    
    # Eager load members for response
    await db.refresh(project)
    result = await db.execute(
        select(ProjectModel)
        .where(ProjectModel.id == project.id)
        .options(selectinload(ProjectModel.members).selectinload(ProjectMember.user))
    )
    project = result.scalar_one()
    
    return project


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific project"""
    query = (
        select(ProjectModel)
        .where(
            (ProjectModel.id == project_id)
            & (ProjectModel.organization_id == current_user.organization_id)
        )
        .options(selectinload(ProjectModel.members).selectinload(ProjectMember.user))
    )
    
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


@router.put("/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a project"""
    query = select(ProjectModel).where(
        (ProjectModel.id == project_id) &
        (ProjectModel.organization_id == current_user.organization_id)
    )
    
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Update project fields (excluding members)
    update_data = project_data.model_dump(exclude_unset=True, exclude={"members"})
    for field, value in update_data.items():
        setattr(project, field, value)

    # Sync members if provided
    if project_data.members is not None:
        # Load existing members for the project
        mem_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == project.id)
        )
        existing_members = {m.user_id: m for m in mem_result.scalars().all()}
        incoming = {m.user_id: m for m in project_data.members}

        # Ensure owner membership persists
        owner_user_id = project.owner_id

        # Add or update members
        for user_id, m in incoming.items():
            if user_id in existing_members:
                em = existing_members[user_id]
                em.role = m.role or em.role
                em.can_edit_project = bool(m.can_edit_project if m.can_edit_project is not None else em.can_edit_project)
                em.can_create_tasks = bool(m.can_create_tasks if m.can_create_tasks is not None else em.can_create_tasks)
                em.can_assign_tasks = bool(m.can_assign_tasks if m.can_assign_tasks is not None else em.can_assign_tasks)
                em.can_delete_tasks = bool(m.can_delete_tasks if m.can_delete_tasks is not None else em.can_delete_tasks)
            else:
                # Ensure the member user exists in the tenant DB (clone from master if needed)
                t_res = await db.execute(select(User).where(User.id == user_id))
                t_user = t_res.scalar_one_or_none()
                if not t_user:
                    master_session = await tenant_manager.get_master_session()
                    try:
                        m_res = await master_session.execute(select(User).where(User.id == user_id))
                        m_user = m_res.scalar_one_or_none()
                        if not m_user:
                            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Member user not found: {user_id}")
                        clone_user = User(
                            id=m_user.id,
                            email=m_user.email,
                            username=m_user.username,
                            first_name=m_user.first_name,
                            last_name=m_user.last_name,
                            hashed_password=m_user.hashed_password,
                            organization_id=m_user.organization_id,
                            role=m_user.role,
                            status=m_user.status,
                            is_active=m_user.is_active,
                            is_verified=m_user.is_verified,
                            timezone=m_user.timezone,
                            phone=m_user.phone,
                            bio=m_user.bio,
                            address=getattr(m_user, "address", None),
                            preferences=m_user.preferences,
                            notification_settings=m_user.notification_settings,
                            last_login=m_user.last_login,
                            password_changed_at=m_user.password_changed_at,
                            avatar_url=getattr(m_user, "avatar_url", None),
                        )
                        db.add(clone_user)
                        await db.flush()
                    finally:
                        await master_session.close()
                db.add(
                    ProjectMember(
                        id=str(uuid.uuid4()),
                        project_id=project.id,
                        user_id=user_id,
                        role=m.role or ProjectMemberRole.MEMBER,
                        can_edit_project=bool(m.can_edit_project),
                        can_create_tasks=bool(m.can_create_tasks if m.can_create_tasks is not None else True),
                        can_assign_tasks=bool(m.can_assign_tasks),
                        can_delete_tasks=bool(m.can_delete_tasks),
                    )
                )

        # Remove members not present in incoming (except owner)
        for user_id, em in existing_members.items():
            if (user_id not in incoming) and (user_id != owner_user_id):
                await db.delete(em)

    await db.commit()

    # Reload with relationships for response
    result = await db.execute(
        select(ProjectModel)
        .where(ProjectModel.id == project.id)
        .options(selectinload(ProjectModel.members).selectinload(ProjectMember.user))
    )
    project = result.scalar_one()

    # Real-time broadcast to project channel
    try:
        await ws_send_project_update(
            project.id,
            f"{current_user.first_name} {current_user.last_name}",
            {"event": "project_updated", "fields": list(update_data.keys()), "updated_at": datetime.utcnow().isoformat()},
        )
    except Exception:
        pass
    
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Archive a project (soft delete)"""
    query = select(ProjectModel).where(
        (ProjectModel.id == project_id) &
        (ProjectModel.organization_id == current_user.organization_id)
    )
    
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Soft delete by archiving
    project.is_archived = True
    await db.commit()
