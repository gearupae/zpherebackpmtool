from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from ....api.deps_tenant import get_master_db as get_db
from ....models.user import User
from ....models.organization import Organization
from ....services.admin_analytics_service import AdminAnalyticsService
from ....services.dunning_service import DunningService
from ...deps import get_current_active_user
from ...deps_tenant import require_platform_admin_master as require_platform_admin

router = APIRouter()


@router.get("/tenant-analytics")
async def get_tenant_analytics(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get comprehensive tenant analytics"""
    try:
        analytics = await AdminAnalyticsService.get_tenant_analytics(db)
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tenant analytics: {str(e)}"
        )


@router.get("/revenue-analytics")
async def get_revenue_analytics(
    days: int = Query(90, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get comprehensive revenue analytics"""
    try:
        analytics = await AdminAnalyticsService.get_revenue_analytics(db, days)
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get revenue analytics: {str(e)}"
        )


@router.get("/system-monitoring")
async def get_system_monitoring(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get system performance and monitoring metrics"""
    try:
        monitoring = await AdminAnalyticsService.get_system_monitoring(db)
        return monitoring
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system monitoring: {str(e)}"
        )


@router.get("/customer-support-analytics")
async def get_customer_support_analytics(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get customer support and activity analytics"""
    try:
        analytics = await AdminAnalyticsService.get_customer_support_analytics(db)
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer support analytics: {str(e)}"
        )


@router.get("/dunning-report")
async def get_dunning_report(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get dunning activity report"""
    try:
        report = await DunningService.get_dunning_report(db, days)
        return report
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dunning report: {str(e)}"
        )


@router.post("/process-dunning")
async def process_dunning_events(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Process all pending dunning events"""
    try:
        results = await DunningService.process_dunning_events(db)
        return {
            "message": "Dunning events processed successfully",
            "results": results
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process dunning events: {str(e)}"
        )


@router.get("/subscription-overview")
async def get_subscription_overview(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get subscription overview and key metrics"""
    try:
        from sqlalchemy import select, func, and_
        from ....models.subscription import Subscription, SubscriptionStatus, SubscriptionTier
        
        # Total subscriptions
        total_query = select(func.count(Subscription.id))
        total_result = await db.execute(total_query)
        total_subscriptions = total_result.scalar()
        
        # Active subscriptions
        active_query = select(func.count(Subscription.id)).where(
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
        )
        active_result = await db.execute(active_query)
        active_subscriptions = active_result.scalar()
        
        # Subscriptions by tier
        tier_query = select(
            Subscription.tier,
            func.count(Subscription.id).label("count"),
            func.sum(Subscription.amount).label("revenue")
        ).where(
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
        ).group_by(Subscription.tier)
        
        tier_result = await db.execute(tier_query)
        tier_breakdown = [
            {
                "tier": row.tier,
                "count": row.count,
                "revenue": float(row.revenue / 100) if row.revenue else 0
            }
            for row in tier_result.fetchall()
        ]
        
        # Trial subscriptions
        trial_query = select(func.count(Subscription.id)).where(
            Subscription.status == SubscriptionStatus.TRIALING
        )
        trial_result = await db.execute(trial_query)
        trial_subscriptions = trial_result.scalar()
        
        # Past due subscriptions
        past_due_query = select(func.count(Subscription.id)).where(
            Subscription.status == SubscriptionStatus.PAST_DUE
        )
        past_due_result = await db.execute(past_due_query)
        past_due_subscriptions = past_due_result.scalar()
        
        # New subscriptions this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_query = select(func.count(Subscription.id)).where(
            Subscription.created_at >= month_start
        )
        new_result = await db.execute(new_query)
        new_this_month = new_result.scalar()
        
        return {
            "total_subscriptions": total_subscriptions,
            "active_subscriptions": active_subscriptions,
            "trial_subscriptions": trial_subscriptions,
            "past_due_subscriptions": past_due_subscriptions,
            "new_this_month": new_this_month,
            "tier_breakdown": tier_breakdown,
            "conversion_rate": (active_subscriptions / total_subscriptions * 100) if total_subscriptions > 0 else 0
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get subscription overview: {str(e)}"
        )


@router.get("/revenue-breakdown")
async def get_revenue_breakdown(
    period: str = Query("month", pattern="^(day|week|month|quarter|year)$"),
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get detailed revenue breakdown by period"""
    try:
        from sqlalchemy import select, func, and_, case
        from ....models.subscription import Subscription, SubscriptionStatus
        from ....models.project_invoice import ProjectInvoice, InvoiceStatus
        
        # Calculate date range based on period
        now = datetime.utcnow()
        if period == "day":
            start_date = now - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(weeks=1)
        elif period == "month":
            start_date = now - timedelta(days=30)
        elif period == "quarter":
            start_date = now - timedelta(days=90)
        else:  # year
            start_date = now - timedelta(days=365)
        
        # Subscription revenue
        subscription_revenue_query = select(
            func.sum(Subscription.amount).label("total_revenue")
        ).where(
            and_(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.last_payment_date >= start_date
            )
        )
        subscription_result = await db.execute(subscription_revenue_query)
        subscription_revenue = subscription_result.scalar() or 0
        
        # Project invoice revenue
        invoice_revenue_query = select(
            func.sum(ProjectInvoice.total_amount).label("total_revenue")
        ).where(
            and_(
                ProjectInvoice.status == InvoiceStatus.PAID,
                ProjectInvoice.paid_date >= start_date
            )
        )
        invoice_result = await db.execute(invoice_revenue_query)
        invoice_revenue = invoice_result.scalar() or 0
        
        # Revenue by tier
        tier_revenue_query = select(
            Subscription.tier,
            func.sum(Subscription.amount).label("revenue"),
            func.count(Subscription.id).label("count")
        ).where(
            and_(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.last_payment_date >= start_date
            )
        ).group_by(Subscription.tier)
        
        tier_result = await db.execute(tier_revenue_query)
        tier_revenue = [
            {
                "tier": row.tier,
                "revenue": float(row.revenue / 100) if row.revenue else 0,
                "count": row.count
            }
            for row in tier_result.fetchall()
        ]
        
        # Revenue over time (daily for the period)
        daily_revenue_query = select(
            func.date(Subscription.last_payment_date).label("date"),
            func.sum(Subscription.amount).label("revenue")
        ).where(
            and_(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.last_payment_date >= start_date
            )
        ).group_by(func.date(Subscription.last_payment_date)).order_by(func.date(Subscription.last_payment_date))
        
        daily_result = await db.execute(daily_revenue_query)
        daily_revenue = [
            {
                "date": str(row.date),
                "revenue": float(row.revenue / 100) if row.revenue else 0
            }
            for row in daily_result.fetchall()
        ]
        
        total_revenue = (subscription_revenue + invoice_revenue) / 100  # Convert from cents
        
        return {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": now.isoformat(),
            "total_revenue": total_revenue,
            "subscription_revenue": float(subscription_revenue / 100),
            "invoice_revenue": float(invoice_revenue / 100),
            "tier_breakdown": tier_revenue,
            "daily_revenue": daily_revenue
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get revenue breakdown: {str(e)}"
        )


@router.get("/usage-metrics")
async def get_usage_metrics(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get detailed usage metrics across all organizations"""
    try:
        from sqlalchemy import select, func, and_
        from ....models.subscription import Subscription
        from ....models.project import Project
        from ....models.task import Task
        from ....models.user import User
        from ....models.customer import Customer
        
        # Storage usage
        storage_query = select(
            func.sum(Subscription.storage_used_mb).label("total_storage_mb"),
            func.avg(Subscription.storage_used_mb).label("avg_storage_mb"),
            func.max(Subscription.storage_used_mb).label("max_storage_mb")
        )
        storage_result = await db.execute(storage_query)
        storage_stats = storage_result.first()
        
        # User usage
        user_query = select(
            func.sum(Subscription.user_count).label("total_users"),
            func.avg(Subscription.user_count).label("avg_users_per_org")
        )
        user_result = await db.execute(user_query)
        user_stats = user_result.first()
        
        # Project usage
        project_query = select(
            func.count(Project.id).label("total_projects"),
            func.avg(func.count(Project.id)).over().label("avg_projects_per_org")
        ).group_by(Project.organization_id)
        project_result = await db.execute(project_query)
        project_stats = project_result.first()
        
        # Task usage
        task_query = select(
            func.count(Task.id).label("total_tasks"),
            func.avg(func.count(Task.id)).over().label("avg_tasks_per_org")
        ).group_by(Task.project_id)
        task_result = await db.execute(task_query)
        task_stats = task_result.first()
        
        # Customer usage
        customer_query = select(
            func.count(Customer.id).label("total_customers"),
            func.avg(func.count(Customer.id)).over().label("avg_customers_per_org")
        ).group_by(Customer.organization_id)
        customer_result = await db.execute(customer_query)
        customer_stats = customer_result.first()
        
        return {
            "storage": {
                "total_mb": storage_stats.total_storage_mb or 0,
                "avg_mb_per_org": storage_stats.avg_storage_mb or 0,
                "max_mb_per_org": storage_stats.max_storage_mb or 0
            },
            "users": {
                "total": user_stats.total_users or 0,
                "avg_per_org": user_stats.avg_users_per_org or 0
            },
            "projects": {
                "total": project_stats.total_projects or 0,
                "avg_per_org": project_stats.avg_projects_per_org or 0
            },
            "tasks": {
                "total": task_stats.total_tasks or 0,
                "avg_per_org": task_stats.avg_tasks_per_org or 0
            },
            "customers": {
                "total": customer_stats.total_customers or 0,
                "avg_per_org": customer_stats.avg_customers_per_org or 0
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get usage metrics: {str(e)}"
        )


@router.get("/churn-analysis")
async def get_churn_analysis(
    days: int = Query(90, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get detailed churn analysis"""
    try:
        from sqlalchemy import select, func, and_
        from ....models.subscription import Subscription, SubscriptionStatus
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Cancelled subscriptions in period
        cancelled_query = select(
            func.count(Subscription.id).label("cancelled_count"),
            func.avg(func.extract('day', Subscription.cancelled_at - Subscription.created_at)).label("avg_lifetime_days")
        ).where(
            and_(
                Subscription.cancelled_at >= start_date,
                Subscription.status == SubscriptionStatus.CANCELLED
            )
        )
        cancelled_result = await db.execute(cancelled_query)
        cancelled_stats = cancelled_result.first()
        
        # Active subscriptions at start of period
        active_at_start_query = select(func.count(Subscription.id)).where(
            and_(
                Subscription.created_at < start_date,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
            )
        )
        active_at_start_result = await db.execute(active_at_start_query)
        active_at_start = active_at_start_result.scalar()
        
        # Churn rate calculation
        churn_rate = 0
        if active_at_start and active_at_start > 0:
            churn_rate = (cancelled_stats.cancelled_count / active_at_start) * 100
        
        # Churn by tier
        churn_by_tier_query = select(
            Subscription.tier,
            func.count(Subscription.id).label("cancelled_count")
        ).where(
            and_(
                Subscription.cancelled_at >= start_date,
                Subscription.status == SubscriptionStatus.CANCELLED
            )
        ).group_by(Subscription.tier)
        
        churn_tier_result = await db.execute(churn_by_tier_query)
        churn_by_tier = [
            {
                "tier": row.tier,
                "cancelled_count": row.cancelled_count
            }
            for row in churn_tier_result.fetchall()
        ]
        
        return {
            "period_days": days,
            "cancelled_count": cancelled_stats.cancelled_count or 0,
            "active_at_start": active_at_start or 0,
            "churn_rate": churn_rate,
            "avg_lifetime_days": cancelled_stats.avg_lifetime_days or 0,
            "churn_by_tier": churn_by_tier
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get churn analysis: {str(e)}"
        )
