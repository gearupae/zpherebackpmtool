from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, Response
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
from ....models.user import User
from ....models.project import Project, ProjectStatus
from ....models.task import Task, TaskStatus, TaskPriority
from ....models.customer import Customer
from ....models.project_invoice import ProjectInvoice, InvoiceStatus
from ....models.organization import Organization
from ...deps import get_current_active_user, get_current_organization

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_analytics(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
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


@router.get("/predictive")
async def get_predictive_analytics(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
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
