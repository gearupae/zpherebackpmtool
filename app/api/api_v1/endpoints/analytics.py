from typing import Any, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, text
from datetime import datetime, timedelta
import calendar
import uuid
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO

from ....db.database import get_db
from ....models.user import User, UserRole, UserStatus
from ....models.project import Project, ProjectStatus, ProjectMember
from ....models.task import Task, TaskStatus, TaskPriority, TaskComment
from ....models.project_comment import ProjectComment
from ....models.customer import Customer
from ....models.project_invoice import ProjectInvoice, InvoiceStatus
from ....models.organization import Organization
from ...deps import get_current_active_user, get_current_organization
from ...deps_tenant import get_tenant_db
from ....db.tenant_manager import tenant_manager
from sqlalchemy.orm import selectinload

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_analytics(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get dashboard analytics overview"""
    
    # Project statistics
    project_stats_query = select(
        func.count().label("total_projects"),
        func.sum(case((Project.status == ProjectStatus.ACTIVE, 1), else_=0)).label("active_projects"),
        func.sum(case((Project.status == ProjectStatus.COMPLETED, 1), else_=0)).label("completed_projects"),
        func.sum(case((Project.status == ProjectStatus.ON_HOLD, 1), else_=0)).label("on_hold_projects"),
        func.coalesce(func.sum(Project.budget), 0).label("total_budget"),
        func.coalesce(func.avg(Project.budget), 0).label("avg_budget")
    ).where(Project.organization_id == current_org.id)
    
    project_result = await db.execute(project_stats_query)
    project_stats = project_result.first()
    
    # Task statistics
    task_stats_query = select(
        func.count().label("total_tasks"),
        func.sum(case((Task.status == TaskStatus.TODO, 1), else_=0)).label("todo_tasks"),
        func.sum(case((Task.status == TaskStatus.IN_PROGRESS, 1), else_=0)).label("in_progress_tasks"),
        func.sum(case((Task.status == TaskStatus.COMPLETED, 1), else_=0)).label("completed_tasks"),
        func.sum(case((Task.status == TaskStatus.BLOCKED, 1), else_=0)).label("blocked_tasks"),
        func.sum(case((Task.due_date < func.now(), 1), else_=0)).label("overdue_tasks")
    ).select_from(
        Task.join(Project)
    ).where(Project.organization_id == current_org.id)
    
    task_result = await db.execute(task_stats_query)
    task_stats = task_result.first()
    
    # User statistics
    user_stats_query = select(
        func.count().label("total_users"),
        func.sum(case((User.is_active == True, 1), else_=0)).label("active_users")
    ).where(User.organization_id == current_org.id)
    
    user_result = await db.execute(user_stats_query)
    user_stats = user_result.first()
    
    # Customer statistics
    customer_stats_query = select(
        func.count().label("total_customers"),
        func.sum(case((Customer.customer_type == "client", 1), else_=0)).label("clients"),
        func.sum(case((Customer.customer_type == "prospect", 1), else_=0)).label("prospects")
    ).where(Customer.organization_id == current_org.id)
    
    customer_result = await db.execute(customer_stats_query)
    customer_stats = customer_result.first()
    
    # Revenue statistics (from invoices)
    revenue_stats_query = select(
        func.coalesce(func.sum(ProjectInvoice.total_amount), 0).label("total_revenue"),
        func.coalesce(func.sum(case((ProjectInvoice.status == InvoiceStatus.PAID, ProjectInvoice.total_amount), else_=0)), 0).label("paid_revenue"),
        func.coalesce(func.sum(case((ProjectInvoice.status == InvoiceStatus.PENDING, ProjectInvoice.total_amount), else_=0)), 0).label("pending_revenue"),
        func.count().label("total_invoices")
    ).where(ProjectInvoice.organization_id == current_org.id)
    
    revenue_result = await db.execute(revenue_stats_query)
    revenue_stats = revenue_result.first()
    
    return {
        "projects": {
            "total": project_stats.total_projects or 0,
            "active": project_stats.active_projects or 0,
            "completed": project_stats.completed_projects or 0,
            "on_hold": project_stats.on_hold_projects or 0,
            "total_budget": project_stats.total_budget or 0,
            "avg_budget": float(project_stats.avg_budget or 0)
        },
        "tasks": {
            "total": task_stats.total_tasks or 0,
            "todo": task_stats.todo_tasks or 0,
            "in_progress": task_stats.in_progress_tasks or 0,
            "completed": task_stats.completed_tasks or 0,
            "blocked": task_stats.blocked_tasks or 0,
            "overdue": task_stats.overdue_tasks or 0
        },
        "users": {
            "total": user_stats.total_users or 0,
            "active": user_stats.active_users or 0
        },
        "customers": {
            "total": customer_stats.total_customers or 0,
            "clients": customer_stats.clients or 0,
            "prospects": customer_stats.prospects or 0
        },
        "revenue": {
            "total": revenue_stats.total_revenue or 0,
            "paid": revenue_stats.paid_revenue or 0,
            "pending": revenue_stats.pending_revenue or 0,
            "invoices": revenue_stats.total_invoices or 0
        }
    }


@router.get("/projects")
async def get_project_analytics(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
db: AsyncSession = Depends(get_tenant_db),
    days: int = Query(30, ge=1, le=365),
) -> Any:
    """Get project analytics over time"""
    
    start_date = datetime.now() - timedelta(days=days)
    
    # Project completion over time
    completion_query = select(
        func.date(Project.completed_date).label("date"),
        func.count().label("completed_count")
    ).where(
        and_(
            Project.organization_id == current_org.id,
            Project.completed_date >= start_date,
            Project.status == ProjectStatus.COMPLETED
        )
    ).group_by(func.date(Project.completed_date)).order_by(func.date(Project.completed_date))
    
    completion_result = await db.execute(completion_query)
    completion_data = completion_result.fetchall()
    
    # Project status distribution
    status_query = select(
        Project.status,
        func.count().label("count")
    ).where(Project.organization_id == current_org.id).group_by(Project.status)
    
    status_result = await db.execute(status_query)
    status_data = status_result.fetchall()
    
    # Budget vs actual spending
    budget_query = select(
        Project.name,
        Project.budget,
        func.coalesce(func.sum(Task.actual_hours * Project.hourly_rate), 0).label("actual_cost")
    ).select_from(
        Project.outerjoin(Task)
    ).where(
        Project.organization_id == current_org.id
    ).group_by(Project.id, Project.name, Project.budget)
    
    budget_result = await db.execute(budget_query)
    budget_data = budget_result.fetchall()
    
    return {
        "completion_over_time": [
            {"date": str(row.date), "completed": row.completed_count}
            for row in completion_data
        ],
        "status_distribution": [
            {"status": row.status, "count": row.count}
            for row in status_data
        ],
        "budget_analysis": [
            {
                "project": row.name,
                "budget": row.budget or 0,
                "actual_cost": float(row.actual_cost or 0),
                "variance": (row.budget or 0) - float(row.actual_cost or 0)
            }
            for row in budget_data
        ]
    }


@router.get("/tasks")
async def get_task_analytics(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
    days: int = Query(30, ge=1, le=365),
) -> Any:
    """Get task analytics"""
    
    start_date = datetime.now() - timedelta(days=days)
    
    # Task completion over time
    completion_query = select(
        func.date(Task.completed_date).label("date"),
        func.count().label("completed_count")
    ).select_from(
        Task.join(Project)
    ).where(
        and_(
            Project.organization_id == current_org.id,
            Task.completed_date >= start_date,
            Task.status == TaskStatus.COMPLETED
        )
    ).group_by(func.date(Task.completed_date)).order_by(func.date(Task.completed_date))
    
    completion_result = await db.execute(completion_query)
    completion_data = completion_result.fetchall()
    
    # Task priority distribution
    priority_query = select(
        Task.priority,
        func.count().label("count")
    ).select_from(
        Task.join(Project)
    ).where(
        Project.organization_id == current_org.id
    ).group_by(Task.priority)
    
    priority_result = await db.execute(priority_query)
    priority_data = priority_result.fetchall()
    
    # User productivity (tasks completed)
    productivity_query = select(
        User.first_name,
        User.last_name,
        func.count().label("tasks_completed"),
        func.coalesce(func.sum(Task.actual_hours), 0).label("total_hours")
    ).select_from(
        Task.join(Project).join(User, Task.assignee_id == User.id)
    ).where(
        and_(
            Project.organization_id == current_org.id,
            Task.status == TaskStatus.COMPLETED,
            Task.completed_date >= start_date
        )
    ).group_by(User.id, User.first_name, User.last_name)
    
    productivity_result = await db.execute(productivity_query)
    productivity_data = productivity_result.fetchall()
    
    return {
        "completion_over_time": [
            {"date": str(row.date), "completed": row.completed_count}
            for row in completion_data
        ],
        "priority_distribution": [
            {"priority": row.priority, "count": row.count}
            for row in priority_data
        ],
        "user_productivity": [
            {
                "user": f"{row.first_name} {row.last_name}",
                "tasks_completed": row.tasks_completed,
                "total_hours": float(row.total_hours or 0)
            }
            for row in productivity_data
        ]
    }


@router.get("/users")
async def get_user_analytics(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get user performance analytics"""
    
    # User task statistics
    user_stats_query = select(
        User.id,
        User.first_name,
        User.last_name,
        User.email,
        func.count(Task.id).label("total_tasks"),
        func.sum(case((Task.status == TaskStatus.COMPLETED, 1), else_=0)).label("completed_tasks"),
        func.sum(case((Task.status == TaskStatus.IN_PROGRESS, 1), else_=0)).label("in_progress_tasks"),
        func.sum(case((Task.due_date < func.now(), 1), else_=0)).label("overdue_tasks"),
        func.coalesce(func.sum(Task.actual_hours), 0).label("total_hours")
    ).select_from(
        User.outerjoin(Task, Task.assignee_id == User.id).outerjoin(Project)
    ).where(
        User.organization_id == current_org.id
    ).group_by(User.id, User.first_name, User.last_name, User.email)
    
    user_result = await db.execute(user_stats_query)
    user_data = user_result.fetchall()
    
    return {
        "users": [
            {
                "id": row.id,
                "name": f"{row.first_name} {row.last_name}",
                "email": row.email,
                "total_tasks": row.total_tasks,
                "completed_tasks": row.completed_tasks,
                "in_progress_tasks": row.in_progress_tasks,
                "overdue_tasks": row.overdue_tasks,
                "total_hours": float(row.total_hours or 0),
                "completion_rate": (row.completed_tasks / max(row.total_tasks, 1)) * 100
            }
            for row in user_data
        ]
    }


@router.get("/revenue")
async def get_revenue_analytics(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
    days: int = Query(90, ge=1, le=365),
) -> Any:
    """Get revenue analytics"""
    
    start_date = datetime.now() - timedelta(days=days)
    
    # Revenue over time
    revenue_query = select(
        func.date(ProjectInvoice.paid_date).label("date"),
        func.coalesce(func.sum(ProjectInvoice.total_amount), 0).label("revenue")
    ).where(
        and_(
            ProjectInvoice.organization_id == current_org.id,
            ProjectInvoice.status == InvoiceStatus.PAID,
            ProjectInvoice.paid_date >= start_date
        )
    ).group_by(func.date(ProjectInvoice.paid_date)).order_by(func.date(ProjectInvoice.paid_date))
    
    revenue_result = await db.execute(revenue_query)
    revenue_data = revenue_result.fetchall()
    
    # Revenue by customer
    customer_revenue_query = select(
        Customer.company_name,
        Customer.first_name,
        Customer.last_name,
        func.coalesce(func.sum(ProjectInvoice.total_amount), 0).label("total_revenue"),
        func.count(ProjectInvoice.id).label("invoice_count")
    ).select_from(
        ProjectInvoice.join(Customer)
    ).where(
        and_(
            ProjectInvoice.organization_id == current_org.id,
            ProjectInvoice.status == InvoiceStatus.PAID
        )
    ).group_by(Customer.id, Customer.company_name, Customer.first_name, Customer.last_name)
    
    customer_result = await db.execute(customer_revenue_query)
    customer_data = customer_result.fetchall()
    
    # Monthly recurring revenue (MRR) - simplified
    mrr_query = select(
        func.coalesce(func.sum(ProjectInvoice.total_amount), 0).label("mrr")
    ).where(
        and_(
            ProjectInvoice.organization_id == current_org.id,
            ProjectInvoice.status == InvoiceStatus.PAID,
            ProjectInvoice.is_recurring == True
        )
    )
    
    mrr_result = await db.execute(mrr_query)
    mrr = mrr_result.scalar() or 0
    
    return {
        "revenue_over_time": [
            {"date": str(row.date), "revenue": float(row.revenue)}
            for row in revenue_data
        ],
        "revenue_by_customer": [
            {
                "customer": row.company_name or f"{row.first_name} {row.last_name}",
                "revenue": float(row.total_revenue),
                "invoices": row.invoice_count
            }
            for row in customer_data
        ],
        "monthly_recurring_revenue": float(mrr)
    }


@router.get("/export/pdf/dashboard")
async def export_dashboard_pdf(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Response:
    """Export dashboard analytics as PDF"""
    
    # Get dashboard data
    dashboard_data = await get_dashboard_analytics(current_user, current_org, db)
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1  # Center
    )
    story.append(Paragraph(f"{current_org.name} - Dashboard Report", title_style))
    story.append(Spacer(1, 20))
    
    # Date
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Projects Summary
    story.append(Paragraph("Projects Overview", styles['Heading2']))
    project_data = [
        ['Metric', 'Count'],
        ['Total Projects', dashboard_data['projects']['total']],
        ['Active Projects', dashboard_data['projects']['active']],
        ['Completed Projects', dashboard_data['projects']['completed']],
        ['Overdue Projects', dashboard_data['projects']['overdue']]
    ]
    project_table = Table(project_data)
    project_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(project_table)
    story.append(Spacer(1, 20))
    
    # Tasks Summary
    story.append(Paragraph("Tasks Overview", styles['Heading2']))
    task_data = [
        ['Metric', 'Count'],
        ['Total Tasks', dashboard_data['tasks']['total']],
        ['Completed Tasks', dashboard_data['tasks']['completed']],
        ['Pending Tasks', dashboard_data['tasks']['pending']],
        ['Overdue Tasks', dashboard_data['tasks']['overdue']]
    ]
    task_table = Table(task_data)
    task_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(task_table)
    story.append(Spacer(1, 20))
    
    # Revenue Summary
    story.append(Paragraph("Revenue Overview", styles['Heading2']))
    revenue_data = [
        ['Metric', 'Amount'],
        ['Total Revenue', f"${dashboard_data['revenue']['total']/100:.2f}"],
        ['Paid Revenue', f"${dashboard_data['revenue']['paid']/100:.2f}"],
        ['Pending Revenue', f"${dashboard_data['revenue']['pending']/100:.2f}"],
        ['Monthly Recurring', f"${dashboard_data['revenue']['monthly_recurring_revenue']/100:.2f}"]
    ]
    revenue_table = Table(revenue_data)
    revenue_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(revenue_table)
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    # Generate unique filename
    filename = f"dashboard_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/reports/share/project/{project_id}")
async def create_shareable_project_report(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a shareable project report link"""
    
    # Verify project exists and belongs to user's org
    project_query = select(Project).where(
        and_(
            Project.id == project_id,
            Project.organization_id == current_org.id
        )
    )
    
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Generate unique share ID
    share_id = f"project_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{current_org.id}"
    
    # In a real implementation, you'd store this in the database
    # For now, return a mock response
    share_url = f"/shared/project/{share_id}"
    
    return {
        "message": "Shareable project report link created successfully",
        "share_id": share_id,
        "share_url": share_url,
        "project_name": project.name,
        "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
        "created_by": f"{current_user.first_name} {current_user.last_name}",
        "organization": current_org.name
    }


@router.post("/reports/share")
async def create_shareable_report(
    report_data: dict,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a shareable link for a report"""
    import secrets
    
    # Generate unique share ID
    share_id = secrets.token_urlsafe(32)
    
    # Store report data with expiration (e.g., 30 days)
    from datetime import datetime, timedelta
    expiry_date = datetime.now() + timedelta(days=30)
    
    # In a real implementation, you'd store this in a database
    # For now, we'll return the share ID and metadata
    
    share_link = f"/api/v1/analytics/reports/shared/{share_id}"
    
    return {
        "share_id": share_id,
        "share_link": share_link,
        "public_url": f"https://your-domain.com/shared-reports/{share_id}",
        "expires_at": expiry_date.isoformat(),
        "report_type": report_data.get("type", "dashboard"),
        "created_by": f"{current_user.first_name} {current_user.last_name}",
        "organization": current_org.name
    }


@router.get("/shared/project/{share_id}")
async def get_shared_project(
    share_id: str,
) -> Any:
    """Get a shared project by share ID (public endpoint - no auth required)"""
    
    # Extract project_id from share_id (format: project_{project_uuid}_{timestamp}_{org_uuid})
    try:
        # Split by '_' but be careful with UUIDs that contain hyphens
        if not share_id.startswith('project_'):
            raise HTTPException(status_code=404, detail="Invalid share link format")
        
        # Remove 'project_' prefix
        remaining = share_id[8:]  # len('project_') = 8
        
        # Find the project UUID (36 chars: 8-4-4-4-12)
        if len(remaining) < 36:
            raise HTTPException(status_code=404, detail="Invalid share link format")
        
        project_id = remaining[:36]
        remaining = remaining[37:]  # Skip UUID and underscore
        
        # Find timestamp (format: YYYYMMDD_HHMMSS = 15 chars)
        if len(remaining) < 15:
            raise HTTPException(status_code=404, detail="Invalid share link format")
        
        timestamp = remaining[:15]
        remaining = remaining[16:]  # Skip timestamp and underscore
        
        # Remaining should be org UUID (36 chars)
        if len(remaining) != 36:
            raise HTTPException(status_code=404, detail="Invalid share link format")
        
        org_id = remaining
        
    except (ValueError, IndexError):
        raise HTTPException(status_code=404, detail="Invalid share link")
    
    # Get project data (no auth check since this is public) from the tenant DB for the given org
    try:
        session = await tenant_manager.get_tenant_session(org_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Invalid or expired share link")

    try:
        project_query = select(Project).where(
            and_(
                Project.id == project_id,
                Project.organization_id == org_id
            )
        )
        project_result = await session.execute(project_query)
        project = project_result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or link expired")
        
        # Get project tasks (only those visible to customer)
        tasks_query = (
            select(Task)
            .options(selectinload(Task.comments))
            .where(
                and_(
                    Task.project_id == project_id,
                    Task.visible_to_customer == True
                )
            )
        )
        tasks_result = await session.execute(tasks_query)
        tasks = tasks_result.scalars().all()

        # Get team members with user info
        members_query = (
            select(ProjectMember)
            .where(ProjectMember.project_id == project_id)
            .options(selectinload(ProjectMember.user))
        )
        members_result = await session.execute(members_query)
        members = members_result.scalars().all()

        # Get organization info
        org_query = select(Organization).where(Organization.id == org_id)
        org_result = await session.execute(org_query)
        organization = org_result.scalar_one_or_none()

        # Get customer info (if any)
        customer = None
        if project.customer_id:
            cust_res = await session.execute(select(Customer).where(Customer.id == project.customer_id))
            customer = cust_res.scalar_one_or_none()
        
        # Get project comments (only approved public comments)
        project_comments_query = (
            select(ProjectComment)
            .options(selectinload(ProjectComment.user))
            .where(
                and_(
                    ProjectComment.project_id == project_id,
                    ProjectComment.is_public == True,
                    ProjectComment.is_approved == True,
                    ProjectComment.is_deleted == False
                )
            )
            .order_by(ProjectComment.created_at.desc())
        )
        project_comments_result = await session.execute(project_comments_query)
        project_comments = project_comments_result.scalars().all()
    finally:
        await session.close()
    
    return {
        "message": "Shared project accessed successfully",
        "share_id": share_id,
        "public_access": True,
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "priority": project.priority,
            "budget": project.budget,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "due_date": project.due_date.isoformat() if project.due_date else None,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
        },
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "created_at": task.created_at.isoformat(),
                "comments": [
                    {
                        "id": c.id,
                        "content": c.content,
                        "created_at": c.created_at.isoformat(),
                    }
                    for c in task.comments
                ]
            }
            for task in tasks
        ],
        "team": {
            "members": [
                {
                    "id": pm.id,
                    "user_id": pm.user_id,
                    "role": pm.role,
                    "user": {
                        "id": pm.user.id if pm.user else None,
                        "first_name": getattr(pm.user, "first_name", None) if pm.user else None,
                        "last_name": getattr(pm.user, "last_name", None) if pm.user else None,
                        "full_name": getattr(pm.user, "full_name", None) if pm.user else None,
                        "email": getattr(pm.user, "email", None) if pm.user else None,
                        "avatar_url": getattr(pm.user, "avatar_url", None) if pm.user else None,
                    },
                }
                for pm in members
            ],
            "count": len(members),
        },
        "organization": {
            "name": organization.name if organization else "Unknown Organization"
        },
        "customer": (
            {
                "id": customer.id,
                "display_name": getattr(customer, "display_name", None) if customer else None,
                "company_name": getattr(customer, "company_name", None) if customer else None,
                "email": getattr(customer, "email", None) if customer else None,
            }
            if customer
            else None
        ),
        "project_comments": [
            {
                "id": comment.id,
                "content": comment.content,
                "author_name": comment.display_author,
                "is_public": comment.is_public,
                "created_at": comment.created_at.isoformat(),
            }
            for comment in project_comments
        ],
        "generated_at": datetime.now().isoformat()
    }


class PublicCommentIn(BaseModel):
    content: str
    name: Optional[str] = None
    email: Optional[str] = None


@router.post("/shared/project/{share_id}/tasks/{task_id}/comments")
async def post_public_task_comment(
    share_id: str,
    task_id: str,
    comment_in: PublicCommentIn,
) -> Any:
    """Post a public comment to a task via share link (no auth)."""
    # Parse share_id similar to get_shared_project
    try:
        if not share_id.startswith('project_'):
            raise HTTPException(status_code=404, detail="Invalid share link format")
        remaining = share_id[8:]
        if len(remaining) < 36:
            raise HTTPException(status_code=404, detail="Invalid share link format")
        project_id = remaining[:36]
        remaining = remaining[37:]
        if len(remaining) < 15:
            raise HTTPException(status_code=404, detail="Invalid share link format")
        remaining = remaining[16:]
        if len(remaining) != 36:
            raise HTTPException(status_code=404, detail="Invalid share link format")
        org_id = remaining
    except (ValueError, IndexError):
        raise HTTPException(status_code=404, detail="Invalid share link")

    # Get tenant session
    try:
        session = await tenant_manager.get_tenant_session(org_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Invalid or expired share link")

    # Validate task belongs to project and is visible
    from sqlalchemy import select as sa_select
    try:
        project_res = await session.execute(sa_select(Project).where(Project.id == project_id))
        project = project_res.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        task_res = await session.execute(sa_select(Task).where(Task.id == task_id, Task.project_id == project_id))
        task = task_res.scalar_one_or_none()
        if not task or not task.visible_to_customer:
            raise HTTPException(status_code=403, detail="Task not visible")

        # Ensure a public guest user exists in this tenant
        guest_email = f"public-guest+{org_id}@public.local"
        user_res = await session.execute(sa_select(User).where(User.email == guest_email))
        guest = user_res.scalar_one_or_none()
        if not guest:
            import uuid as _uuid
            guest = User(
                id=str(_uuid.uuid4()),
                email=guest_email,
                username=f"public_guest_{org_id[:8]}",
                first_name="Public",
                last_name="Guest",
                hashed_password="!",
                organization_id=org_id,
                role=UserRole.CLIENT,
                is_active=True,
                is_verified=False,
                status=UserStatus.ACTIVE,
                preferences={},
                notification_settings={},
            )
            session.add(guest)
            await session.flush()

        # Create public comment
        import uuid as _uuid
        display_name = (comment_in.name or "Guest").strip()[:100]
        email_note = f" ({comment_in.email})" if comment_in.email else ""
        content_text = comment_in.content.strip()
        if not content_text:
            raise HTTPException(status_code=422, detail="Content required")
        content_stored = f"[Public] {display_name}{email_note}: {content_text}"

        comment = TaskComment(
            id=str(_uuid.uuid4()),
            task_id=task.id,
            user_id=guest.id,
            content=content_stored,
            mentions=[],
            linked_tasks=[],
        )
        session.add(comment)
        await session.commit()
        await session.refresh(comment)

        # Return minimal info
        return {
            "id": comment.id,
            "content": comment.content,
            "created_at": comment.created_at.isoformat(),
        }
    except HTTPException:
        await session.rollback()
        await session.close()
        raise
    except Exception:
        await session.rollback()
        await session.close()
        raise HTTPException(status_code=500, detail="Internal error")
    finally:
        try:
            await session.close()
        except Exception:
            pass


@router.post("/shared/project/{share_id}/comments")
async def post_public_project_comment(
    share_id: str,
    comment_in: PublicCommentIn,
) -> Any:
    """Post a public comment to a project via share link (no auth).
    Additionally, mirror the comment as a TaskComment on a "Public Feedback (Shared)" task
    so it appears in the internal dashboard under a corresponding task.
    """
    # Parse share_id similar to get_shared_project
    try:
        if not share_id.startswith('project_'):
            raise HTTPException(status_code=404, detail="Invalid share link format")
        remaining = share_id[8:]
        if len(remaining) < 36:
            raise HTTPException(status_code=404, detail="Invalid share link format")
        project_id = remaining[:36]
        remaining = remaining[37:]
        if len(remaining) < 15:
            raise HTTPException(status_code=404, detail="Invalid share link format")
        remaining = remaining[16:]
        if len(remaining) != 36:
            raise HTTPException(status_code=404, detail="Invalid share link format")
        org_id = remaining
    except (ValueError, IndexError):
        raise HTTPException(status_code=404, detail="Invalid share link")

    # Get tenant session
    try:
        session = await tenant_manager.get_tenant_session(org_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Invalid or expired share link")

    # Validate project exists and create comment + mirrored task comment
    from sqlalchemy import select as sa_select
    try:
        project_res = await session.execute(sa_select(Project).where(Project.id == project_id))
        project = project_res.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Prepare public comment values
        import uuid as _uuid
        display_name = (comment_in.name or "Guest").strip()[:100]
        content_text = comment_in.content.strip()
        if not content_text:
            raise HTTPException(status_code=422, detail="Content required")

        # Ensure a public guest user exists (used for both project and task comments)
        guest_email = f"public-guest+{org_id}@public.local"
        user_res = await session.execute(sa_select(User).where(User.email == guest_email))
        guest = user_res.scalar_one_or_none()
        if not guest:
            guest = User(
                id=str(_uuid.uuid4()),
                email=guest_email,
                username=f"public_guest_{org_id[:8]}",
                first_name="Public",
                last_name="Guest",
                hashed_password="!",
                organization_id=org_id,
                role=UserRole.CLIENT,
                is_active=True,
                is_verified=False,
                status=UserStatus.ACTIVE,
                preferences={},
                notification_settings={},
            )
            session.add(guest)
            await session.flush()

        # Create public project comment (associate with guest user for NOT NULL constraint)
        project_comment = ProjectComment(
            id=str(_uuid.uuid4()),
            project_id=project.id,
            user_id=guest.id,
            content=content_text,
            author_name=display_name,
            author_email=comment_in.email.strip() if comment_in.email else None,
            is_public=True,
            is_approved=True,  # Auto-approve for now
            source_type="public_share",
            share_id=share_id,
        )
        session.add(project_comment)
        # Commit the project comment first to avoid losing it if mirroring fails
        await session.commit()
        await session.refresh(project_comment)

        # Best-effort: mirror as task comment under a container task
        try:

            # Find or create a container task for public feedback under this project
            feedback_title = "Public Feedback (Shared)"
            task_res = await session.execute(
                sa_select(Task).where(
                    (Task.project_id == project_id) & (Task.title == feedback_title)
                )
            )
            feedback_task = task_res.scalar_one_or_none()
            if not feedback_task:
                feedback_task = Task(
                    id=str(_uuid.uuid4()),
                    title=feedback_title,
                    description="Container for public comments submitted via shared project link.",
                    project_id=project.id,
                    status=TaskStatus.TODO,
                    priority=TaskPriority.MEDIUM,
                    created_by_id=guest.id,
                    visible_to_customer=False,
                )
                session.add(feedback_task)
                await session.flush()

            # Mirror the project comment as a TaskComment on the feedback task
            content_mirrored = f"[Public] {display_name}{' (' + comment_in.email + ')' if comment_in.email else ''}: {content_text}"
            task_comment = TaskComment(
                id=str(_uuid.uuid4()),
                task_id=feedback_task.id,
                user_id=guest.id,
                content=content_mirrored,
                mentions=[],
                linked_tasks=[],
            )
            session.add(task_comment)
            await session.commit()
        except Exception:
            await session.rollback()
            # Silently continue; the primary project comment is already saved
            pass

        # Return minimal info for public API
        return {
            "id": project_comment.id,
            "content": project_comment.content,
            "author_name": project_comment.display_author,
            "created_at": project_comment.created_at.isoformat(),
        }
    except HTTPException:
        await session.rollback()
        await session.close()
        raise
    except Exception:
        await session.rollback()
        await session.close()
        raise HTTPException(status_code=500, detail="Internal error")
    finally:
        try:
            await session.close()
        except Exception:
            pass


@router.post("/reports/shared/{share_id}")
async def get_shared_report(
    share_id: str,
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a shared report by share ID (public endpoint)"""
    
    # In a real implementation, you'd:
    # 1. Look up the share_id in the database
    # 2. Check if it's not expired
    # 3. Return the report data
    
    # For now, return a sample response
    return {
        "message": "Shared report accessed",
        "share_id": share_id,
        "report_data": {
            "title": "Project Dashboard Report",
            "generated_at": datetime.now().isoformat(),
            "data": {
                "projects": {"total": 5, "active": 3, "completed": 2},
                "tasks": {"total": 25, "completed": 18, "pending": 7},
                "team": {"members": 8, "utilization": 85}
            }
        },
        "public_access": True
    }


@router.get("/export/pdf/project/{project_id}")
async def export_project_pdf(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Response:
    """Export individual project report as PDF"""
    
    # Get project data
    project_query = select(Project).where(
        and_(
            Project.id == project_id,
            Project.organization_id == current_org.id
        )
    )
    
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get project tasks
    tasks_query = select(Task).where(Task.project_id == project_id)
    tasks_result = await db.execute(tasks_query)
    tasks = tasks_result.scalars().all()
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1  # Center
    )
    story.append(Paragraph(f"Project Report: {project.name}", title_style))
    story.append(Spacer(1, 20))
    
    # Project Details
    story.append(Paragraph("Project Overview", styles['Heading2']))
    
    project_details = [
        ['Field', 'Value'],
        ['Project Name', project.name],
        ['Description', project.description or 'No description'],
        ['Status', project.status.replace('_', ' ').title()],
        ['Priority', project.priority.title()],
        ['Budget', f"${project.budget/100:.2f}" if project.budget else 'No budget'],
        ['Start Date', project.start_date.strftime('%Y-%m-%d') if project.start_date else 'Not set'],
        ['Due Date', project.due_date.strftime('%Y-%m-%d') if project.due_date else 'Not set'],
        ['Created', project.created_at.strftime('%Y-%m-%d %H:%M')],
        ['Last Updated', project.updated_at.strftime('%Y-%m-%d %H:%M')],
    ]
    
    project_table = Table(project_details)
    project_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(project_table)
    story.append(Spacer(1, 20))
    
    # Tasks Section
    if tasks:
        story.append(Paragraph("Project Tasks", styles['Heading2']))
        task_data = [
            ['Task Name', 'Status', 'Priority', 'Due Date']
        ]
        
        for task in tasks:
            task_data.append([
                task.title,
                task.status.replace('_', ' ').title(),
                task.priority.title(),
                task.due_date.strftime('%Y-%m-%d') if task.due_date else 'No due date'
            ])
        
        task_table = Table(task_data)
        task_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(task_table)
    else:
        story.append(Paragraph("No tasks found for this project.", styles['Normal']))
    
    story.append(Spacer(1, 20))
    
    # Footer
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    story.append(Paragraph(f"Report created by: {current_user.first_name} {current_user.last_name}", styles['Normal']))
    story.append(Paragraph(f"Organization: {current_org.name}", styles['Normal']))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    # Generate unique filename
    safe_project_name = "".join(c for c in project.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = f"project_{safe_project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/pdf/projects")
async def export_projects_pdf(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_tenant_db),
) -> Response:
    """Export projects report as PDF"""
    
    # Get projects data
    projects_query = select(Project).where(
        and_(
            Project.organization_id == current_org.id,
            Project.is_archived == False
        )
    ).order_by(Project.updated_at.desc())
    
    projects_result = await db.execute(projects_query)
    projects = projects_result.scalars().all()
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1  # Center
    )
    story.append(Paragraph(f"{current_org.name} - Projects Report", title_style))
    story.append(Spacer(1, 20))
    
    # Date
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Projects Table
    story.append(Paragraph("Projects Overview", styles['Heading2']))
    project_data = [
        ['Project Name', 'Status', 'Priority', 'Due Date', 'Budget']
    ]
    
    for project in projects:
        project_data.append([
            project.name,
            project.status.replace('_', ' ').title(),
            project.priority.title(),
            project.due_date.strftime('%Y-%m-%d') if project.due_date else 'No due date',
            f"${project.budget/100:.2f}" if project.budget else 'No budget'
        ])
    
    project_table = Table(project_data)
    project_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(project_table)
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    # Generate unique filename
    filename = f"projects_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/predictive")
async def get_predictive_analytics(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get predictive analytics and deadline predictions"""
    
    # Get all active projects with due dates
    active_projects_query = select(Project).where(
        and_(
            Project.organization_id == current_org.id,
            Project.status.in_([ProjectStatus.ACTIVE, ProjectStatus.PLANNING]),
            Project.due_date.is_not(None)
        )
    )
    
    active_projects_result = await db.execute(active_projects_query)
    active_projects = active_projects_result.scalars().all()
    
    predictions = []
    
    for project in active_projects:
        # Calculate project health score
        project_tasks_query = select(Task).where(Task.project_id == project.id)
        project_tasks_result = await db.execute(project_tasks_query)
        project_tasks = project_tasks_result.scalars().all()
        
        if not project_tasks:
            continue
        
        total_tasks = len(project_tasks)
        completed_tasks = len([t for t in project_tasks if t.status == TaskStatus.COMPLETED])
        overdue_tasks = len([t for t in project_tasks if t.is_overdue])
        
        # Calculate completion rate
        completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
        
        # Calculate days remaining
        days_remaining = (project.due_date - datetime.now()).days if project.due_date else 0
        
        # Calculate estimated completion time based on current progress
        if completion_rate > 0:
            estimated_completion_days = (days_remaining / completion_rate) * 100 if completion_rate > 0 else 0
        else:
            estimated_completion_days = days_remaining
        
        # Determine deadline confidence
        if estimated_completion_days <= days_remaining:
            confidence = "High"
            confidence_score = 90
            will_hit_deadline = True
        elif estimated_completion_days <= days_remaining + 3:
            confidence = "Medium"
            confidence_score = 60
            will_hit_deadline = True
        else:
            confidence = "Low"
            confidence_score = 30
            will_hit_deadline = False
        
        # Calculate risk factors
        risk_factors = []
        if overdue_tasks > 0:
            risk_factors.append(f"{overdue_tasks} overdue tasks")
        if completion_rate < 30 and days_remaining < 14:
            risk_factors.append("Low completion rate with short timeline")
        if estimated_completion_days > days_remaining + 7:
            risk_factors.append("Significant timeline overrun predicted")
        
        # Project health indicator
        if confidence_score >= 80:
            health = "🟢 Green"
        elif confidence_score >= 50:
            health = "🟡 Yellow"
        else:
            health = "🔴 Red"
        
        predictions.append({
            "project_id": project.id,
            "project_name": project.name,
            "due_date": project.due_date.isoformat() if project.due_date else None,
            "days_remaining": days_remaining,
            "completion_rate": round(completion_rate, 1),
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "overdue_tasks": overdue_tasks,
            "estimated_completion_days": round(estimated_completion_days, 1),
            "will_hit_deadline": will_hit_deadline,
            "confidence": confidence,
            "confidence_score": confidence_score,
            "health_indicator": health,
            "risk_factors": risk_factors,
            "recommendations": get_project_recommendations(completion_rate, overdue_tasks, days_remaining)
        })
    
    # Sort by confidence score (lowest first - highest risk)
    predictions.sort(key=lambda x: x["confidence_score"])
    
    # Overall organization health
    total_projects = len(predictions)
    on_track_projects = len([p for p in predictions if p["will_hit_deadline"]])
    at_risk_projects = len([p for p in predictions if p["confidence_score"] < 50])
    
    overall_health = {
        "total_projects": total_projects,
        "on_track": on_track_projects,
        "at_risk": at_risk_projects,
        "success_rate": (on_track_projects / total_projects * 100) if total_projects > 0 else 0,
        "overall_confidence": "🟢 High" if at_risk_projects == 0 else "🟡 Medium" if at_risk_projects <= 2 else "🔴 Low"
    }
    
    return {
        "overall_health": overall_health,
        "project_predictions": predictions,
        "generated_at": datetime.now().isoformat()
    }


def get_project_recommendations(completion_rate: float, overdue_tasks: int, days_remaining: int) -> List[str]:
    """Generate recommendations based on project metrics"""
    recommendations = []
    
    if completion_rate < 30 and days_remaining < 14:
        recommendations.append("Consider extending deadline or adding resources")
        recommendations.append("Prioritize critical path tasks")
    
    if overdue_tasks > 0:
        recommendations.append("Address overdue tasks immediately")
        recommendations.append("Review task dependencies and blockers")
    
    if completion_rate > 70 and days_remaining > 7:
        recommendations.append("Project is on track - maintain current pace")
    
    if days_remaining < 3:
        recommendations.append("Final push needed - focus on completion")
    
    if not recommendations:
        recommendations.append("Monitor progress and adjust as needed")
    
    return recommendations
