import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case, desc, asc
from sqlalchemy.orm import selectinload

from ..models.subscription import Subscription, SubscriptionStatus, SubscriptionTier, DunningStatus
from ..models.organization import Organization
from ..models.user import User
from ..models.project import Project, ProjectStatus
from ..models.task import Task, TaskStatus
from ..models.customer import Customer
from ..models.project_invoice import ProjectInvoice, InvoiceStatus

logger = logging.getLogger(__name__)


class AdminAnalyticsService:
    """Service for admin analytics and system monitoring"""
    
    @staticmethod
    async def get_tenant_analytics(db: AsyncSession) -> Dict[str, Any]:
        """Get comprehensive tenant analytics"""
        try:
            # Organization statistics
            try:
                org_stats = await AdminAnalyticsService._get_organization_stats(db)
            except Exception as e:
                logger.warning(f"Failed to get org stats: {e}")
                org_stats = {"total": 0, "active": 0, "inactive": 0, "growth_rate": 0}
            
            # Subscription statistics - handle case where subscriptions table doesn't exist
            try:
                subscription_stats = await AdminAnalyticsService._get_subscription_stats(db)
            except Exception as e:
                logger.warning(f"Failed to get subscription stats (table may not exist): {e}")
                subscription_stats = {
                    "total": 0,
                    "by_tier": {"starter": 0, "professional": 0, "business": 0, "enterprise": 0},
                    "by_status": {"active": 0, "past_due": 0, "cancelled": 0},
                    "trial_conversions": 0
                }
            
            # User statistics
            try:
                user_stats = await AdminAnalyticsService._get_user_stats(db)
            except Exception as e:
                logger.warning(f"Failed to get user stats: {e}")
                user_stats = {"total": 0, "active": 0, "by_role": {"admin": 0, "manager": 0, "member": 0, "client": 0}}
            
            # Feature adoption - provide mock data
            try:
                feature_adoption = await AdminAnalyticsService._get_feature_adoption(db)
            except Exception as e:
                logger.warning(f"Failed to get feature adoption: {e}")
                feature_adoption = {}
            
            # Usage metrics - provide mock data
            try:
                usage_metrics = await AdminAnalyticsService._get_usage_metrics(db)
            except Exception as e:
                logger.warning(f"Failed to get usage metrics: {e}")
                usage_metrics = {}
            
            return {
                "organizations": org_stats,
                "subscriptions": subscription_stats,
                "users": user_stats,
                "feature_adoption": feature_adoption,
                "usage_metrics": usage_metrics
            }
        except Exception as e:
            logger.error(f"Failed to get tenant analytics: {e}")
            raise
    
    @staticmethod
    async def get_revenue_analytics(db: AsyncSession, days: int = 90) -> Dict[str, Any]:
        """Get comprehensive revenue analytics"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Monthly Recurring Revenue (MRR) - handle subscription table not existing
            try:
                mrr = await AdminAnalyticsService._calculate_mrr(db)
            except Exception as e:
                logger.warning(f"Failed to calculate MRR (subscriptions may not exist): {e}")
                mrr = 0.0
            
            # Annual Recurring Revenue (ARR)
            arr = mrr * 12
            
            # Revenue over time
            try:
                revenue_timeline = await AdminAnalyticsService._get_revenue_timeline(db, start_date)
            except Exception as e:
                logger.warning(f"Failed to get revenue timeline: {e}")
                revenue_timeline = []
            
            # Revenue by tier
            try:
                revenue_by_tier = await AdminAnalyticsService._get_revenue_by_tier(db)
            except Exception as e:
                logger.warning(f"Failed to get revenue by tier: {e}")
                revenue_by_tier = []
            
            # Churn analysis
            try:
                churn_analysis = await AdminAnalyticsService._get_churn_analysis(db, start_date)
            except Exception as e:
                logger.warning(f"Failed to get churn analysis: {e}")
                churn_analysis = {"cancelled_this_period": 0, "active_at_start": 0, "churn_rate": 0}
            
            # Customer Lifetime Value (CLV)
            try:
                clv_analysis = await AdminAnalyticsService._get_clv_analysis(db)
            except Exception as e:
                logger.warning(f"Failed to get CLV analysis: {e}")
                clv_analysis = {"avg_monthly_revenue": 0.0, "avg_lifetime_months": 1.0, "customer_lifetime_value": 0.0}
            
            # Payment analytics
            try:
                payment_analytics = await AdminAnalyticsService._get_payment_analytics(db, start_date)
            except Exception as e:
                logger.warning(f"Failed to get payment analytics: {e}")
                payment_analytics = {"total_payments": 0, "successful_payments": 0, "success_rate": 0, "avg_payment_days": 0}
            
            return {
                "mrr": mrr,
                "arr": arr,
                "revenue_timeline": revenue_timeline,
                "revenue_by_tier": revenue_by_tier,
                "churn_analysis": churn_analysis,
                "clv_analysis": clv_analysis,
                "payment_analytics": payment_analytics
            }
        except Exception as e:
            logger.error(f"Failed to get revenue analytics: {e}")
            raise
    
    @staticmethod
    async def get_system_monitoring(db: AsyncSession) -> Dict[str, Any]:
        """Get system performance and monitoring metrics"""
        try:
            # API usage statistics
            api_usage = await AdminAnalyticsService._get_api_usage_stats(db)
            
            # Storage consumption
            storage_metrics = await AdminAnalyticsService._get_storage_metrics(db)
            
            # Performance metrics
            performance_metrics = await AdminAnalyticsService._get_performance_metrics(db)
            
            # Error rates
            error_metrics = await AdminAnalyticsService._get_error_metrics(db)
            
            # Database metrics
            db_metrics = await AdminAnalyticsService._get_database_metrics(db)
            
            return {
                "api_usage": api_usage,
                "storage_metrics": storage_metrics,
                "performance_metrics": performance_metrics,
                "error_metrics": error_metrics,
                "database_metrics": db_metrics
            }
        except Exception as e:
            logger.error(f"Failed to get system monitoring: {e}")
            raise
    
    @staticmethod
    async def get_customer_support_analytics(db: AsyncSession) -> Dict[str, Any]:
        """Get customer support and activity analytics"""
        try:
            # User activity logs
            user_activity = await AdminAnalyticsService._get_user_activity_logs(db)
            
            # Support ticket metrics
            support_metrics = await AdminAnalyticsService._get_support_metrics(db)
            
            # Customer satisfaction
            satisfaction_metrics = await AdminAnalyticsService._get_satisfaction_metrics(db)
            
            # Feature usage patterns
            usage_patterns = await AdminAnalyticsService._get_usage_patterns(db)
            
            return {
                "user_activity": user_activity,
                "support_metrics": support_metrics,
                "satisfaction_metrics": satisfaction_metrics,
                "usage_patterns": usage_patterns
            }
        except Exception as e:
            logger.error(f"Failed to get customer support analytics: {e}")
            raise
    
    # Private helper methods
    
    @staticmethod
    async def _get_organization_stats(db: AsyncSession) -> Dict[str, Any]:
        """Get organization statistics"""
        # Total organizations
        total_orgs_query = select(func.count(Organization.id))
        total_orgs_result = await db.execute(total_orgs_query)
        total_orgs = total_orgs_result.scalar()
        
        # Active organizations
        active_orgs_query = select(func.count(Organization.id)).where(Organization.is_active == True)
        active_orgs_result = await db.execute(active_orgs_query)
        active_orgs = active_orgs_result.scalar()
        
        # Organizations by subscription tier
        tier_query = select(
            Subscription.tier,
            func.count(Subscription.id).label("count")
        ).group_by(Subscription.tier)
        tier_result = await db.execute(tier_query)
        tier_stats = {row.tier: row.count for row in tier_result.fetchall()}
        
        # New organizations this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_orgs_query = select(func.count(Organization.id)).where(Organization.created_at >= month_start)
        new_orgs_result = await db.execute(new_orgs_query)
        new_orgs_this_month = new_orgs_result.scalar()
        
        return {
            "total": total_orgs,
            "active": active_orgs,
            "inactive": total_orgs - active_orgs,
            "by_tier": tier_stats,
            "new_this_month": new_orgs_this_month,
            "activation_rate": (active_orgs / total_orgs * 100) if total_orgs > 0 else 0
        }
    
    @staticmethod
    async def _get_subscription_stats(db: AsyncSession) -> Dict[str, Any]:
        """Get subscription statistics"""
        # Total subscriptions
        total_subs_query = select(func.count(Subscription.id))
        total_subs_result = await db.execute(total_subs_query)
        total_subs = total_subs_result.scalar()
        
        # Active subscriptions
        active_subs_query = select(func.count(Subscription.id)).where(
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
        )
        active_subs_result = await db.execute(active_subs_query)
        active_subs = active_subs_result.scalar()
        
        # Subscriptions by status
        status_query = select(
            Subscription.status,
            func.count(Subscription.id).label("count")
        ).group_by(Subscription.status)
        status_result = await db.execute(status_query)
        status_stats = {row.status: row.count for row in status_result.fetchall()}
        
        # Dunning statistics
        dunning_query = select(
            Subscription.dunning_status,
            func.count(Subscription.id).label("count")
        ).where(Subscription.dunning_status != DunningStatus.NONE).group_by(Subscription.dunning_status)
        dunning_result = await db.execute(dunning_query)
        dunning_stats = {row.dunning_status: row.count for row in dunning_result.fetchall()}
        
        return {
            "total": total_subs,
            "active": active_subs,
            "by_status": status_stats,
            "dunning": dunning_stats,
            "conversion_rate": (active_subs / total_subs * 100) if total_subs > 0 else 0
        }
    
    @staticmethod
    async def _get_user_stats(db: AsyncSession) -> Dict[str, Any]:
        """Get user statistics"""
        # Total users
        total_users_query = select(func.count(User.id))
        total_users_result = await db.execute(total_users_query)
        total_users = total_users_result.scalar()
        
        # Active users
        active_users_query = select(func.count(User.id)).where(User.is_active == True)
        active_users_result = await db.execute(active_users_query)
        active_users = active_users_result.scalar()
        
        # Users by role
        role_query = select(
            User.role,
            func.count(User.id).label("count")
        ).group_by(User.role)
        role_result = await db.execute(role_query)
        role_stats = {row.role: row.count for row in role_result.fetchall()}
        
        # New users this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_users_query = select(func.count(User.id)).where(User.created_at >= month_start)
        new_users_result = await db.execute(new_users_query)
        new_users_this_month = new_users_result.scalar()
        
        return {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users,
            "by_role": role_stats,
            "new_this_month": new_users_this_month,
            "activation_rate": (active_users / total_users * 100) if total_users > 0 else 0
        }
    
    @staticmethod
    async def _get_feature_adoption(db: AsyncSession) -> Dict[str, Any]:
        """Get feature adoption statistics"""
        # This would require tracking feature usage in the database
        # For now, we'll return placeholder data
        return {
            "projects": {
                "total_orgs_with_projects": 0,
                "avg_projects_per_org": 0,
                "adoption_rate": 0
            },
            "tasks": {
                "total_orgs_with_tasks": 0,
                "avg_tasks_per_org": 0,
                "adoption_rate": 0
            },
            "invoices": {
                "total_orgs_with_invoices": 0,
                "avg_invoices_per_org": 0,
                "adoption_rate": 0
            },
            "customers": {
                "total_orgs_with_customers": 0,
                "avg_customers_per_org": 0,
                "adoption_rate": 0
            }
        }
    
    @staticmethod
    async def _get_usage_metrics(db: AsyncSession) -> Dict[str, Any]:
        """Get usage metrics"""
        # Storage usage
        storage_query = select(
            func.sum(Subscription.storage_used_mb).label("total_storage_mb"),
            func.avg(Subscription.storage_used_mb).label("avg_storage_mb")
        )
        storage_result = await db.execute(storage_query)
        storage_stats = storage_result.first()
        
        # User usage
        user_usage_query = select(
            func.sum(Subscription.user_count).label("total_users"),
            func.avg(Subscription.user_count).label("avg_users_per_org")
        )
        user_usage_result = await db.execute(user_usage_query)
        user_usage_stats = user_usage_result.first()
        
        # Project usage
        project_query = select(
            func.count(Project.id).label("total_projects"),
            func.avg(func.count(Project.id)).over().label("avg_projects_per_org")
        ).group_by(Project.organization_id)
        project_result = await db.execute(project_query)
        project_stats = project_result.first()
        
        return {
            "storage": {
                "total_mb": storage_stats.total_storage_mb or 0,
                "avg_mb_per_org": storage_stats.avg_storage_mb or 0
            },
            "users": {
                "total": user_usage_stats.total_users or 0,
                "avg_per_org": user_usage_stats.avg_users_per_org or 0
            },
            "projects": {
                "total": project_stats.total_projects or 0,
                "avg_per_org": project_stats.avg_projects_per_org or 0
            }
        }
    
    @staticmethod
    async def _calculate_mrr(db: AsyncSession) -> float:
        """Calculate Monthly Recurring Revenue"""
        mrr_query = select(
            func.sum(Subscription.amount).label("mrr")
        ).where(
            and_(
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]),
                Subscription.interval == "month"
            )
        )
        mrr_result = await db.execute(mrr_query)
        mrr_cents = mrr_result.scalar() or 0
        return mrr_cents / 100  # Convert from cents to dollars
    
    @staticmethod
    async def _get_revenue_timeline(db: AsyncSession, start_date: datetime) -> List[Dict[str, Any]]:
        """Get revenue timeline data"""
        revenue_query = select(
            func.date(Subscription.last_payment_date).label("date"),
            func.sum(Subscription.amount).label("revenue")
        ).where(
            and_(
                Subscription.last_payment_date >= start_date,
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        ).group_by(func.date(Subscription.last_payment_date)).order_by(func.date(Subscription.last_payment_date))
        
        revenue_result = await db.execute(revenue_query)
        return [
            {
                "date": str(row.date),
                "revenue": float(row.revenue / 100) if row.revenue else 0
            }
            for row in revenue_result.fetchall()
        ]
    
    @staticmethod
    async def _get_revenue_by_tier(db: AsyncSession) -> List[Dict[str, Any]]:
        """Get revenue breakdown by subscription tier"""
        tier_revenue_query = select(
            Subscription.tier,
            func.sum(Subscription.amount).label("revenue"),
            func.count(Subscription.id).label("count")
        ).where(
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
        ).group_by(Subscription.tier)
        
        tier_revenue_result = await db.execute(tier_revenue_query)
        return [
            {
                "tier": row.tier,
                "revenue": float(row.revenue / 100) if row.revenue else 0,
                "count": row.count
            }
            for row in tier_revenue_result.fetchall()
        ]
    
    @staticmethod
    async def _get_churn_analysis(db: AsyncSession, start_date: datetime) -> Dict[str, Any]:
        """Get churn analysis"""
        # Cancelled subscriptions this period
        cancelled_query = select(func.count(Subscription.id)).where(
            and_(
                Subscription.cancelled_at >= start_date,
                Subscription.status == SubscriptionStatus.CANCELLED
            )
        )
        cancelled_result = await db.execute(cancelled_query)
        cancelled_count = cancelled_result.scalar()
        
        # Total active subscriptions at start of period
        active_at_start_query = select(func.count(Subscription.id)).where(
            and_(
                Subscription.created_at < start_date,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
            )
        )
        active_at_start_result = await db.execute(active_at_start_query)
        active_at_start = active_at_start_result.scalar()
        
        churn_rate = (cancelled_count / active_at_start * 100) if active_at_start > 0 else 0
        
        return {
            "cancelled_this_period": cancelled_count,
            "active_at_start": active_at_start,
            "churn_rate": churn_rate
        }
    
    @staticmethod
    async def _get_clv_analysis(db: AsyncSession) -> Dict[str, Any]:
        """Get Customer Lifetime Value analysis"""
        # Average subscription amount
        avg_amount_query = select(func.avg(Subscription.amount)).where(
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        avg_amount_result = await db.execute(avg_amount_query)
        avg_amount_cents = avg_amount_result.scalar() or 0
        
        # Average subscription duration (simplified)
        avg_duration_query = select(
            func.avg(func.extract('day', Subscription.current_period_end - Subscription.current_period_start))
        ).where(Subscription.status == SubscriptionStatus.ACTIVE)
        avg_duration_result = await db.execute(avg_duration_query)
        avg_duration_days = avg_duration_result.scalar() or 30
        
        # Calculate CLV (simplified)
        avg_monthly_revenue = avg_amount_cents / 100
        avg_lifetime_months = avg_duration_days / 30
        clv = avg_monthly_revenue * avg_lifetime_months
        
        return {
            "avg_monthly_revenue": avg_monthly_revenue,
            "avg_lifetime_months": avg_lifetime_months,
            "customer_lifetime_value": clv
        }
    
    @staticmethod
    async def _get_payment_analytics(db: AsyncSession, start_date: datetime) -> Dict[str, Any]:
        """Get payment analytics"""
        # Payment success rate
        total_payments_query = select(func.count(ProjectInvoice.id)).where(ProjectInvoice.invoice_date >= start_date)
        total_payments_result = await db.execute(total_payments_query)
        total_payments = total_payments_result.scalar()
        
        successful_payments_query = select(func.count(ProjectInvoice.id)).where(
            and_(
                ProjectInvoice.invoice_date >= start_date,
                ProjectInvoice.status == InvoiceStatus.PAID
            )
        )
        successful_payments_result = await db.execute(successful_payments_query)
        successful_payments = successful_payments_result.scalar()
        
        success_rate = (successful_payments / total_payments * 100) if total_payments > 0 else 0
        
        # Average payment time
        payment_time_query = select(
            func.avg(func.extract('day', ProjectInvoice.paid_date - ProjectInvoice.invoice_date))
        ).where(
            and_(
                ProjectInvoice.paid_date >= start_date,
                ProjectInvoice.status == InvoiceStatus.PAID
            )
        )
        payment_time_result = await db.execute(payment_time_query)
        avg_payment_days = payment_time_result.scalar() or 0
        
        return {
            "total_payments": total_payments,
            "successful_payments": successful_payments,
            "success_rate": success_rate,
            "avg_payment_days": avg_payment_days
        }
    
    @staticmethod
    async def _get_api_usage_stats(db: AsyncSession) -> Dict[str, Any]:
        """Get API usage statistics"""
        # This would require tracking API calls in the database
        # For now, return placeholder data
        return {
            "total_requests": 0,
            "requests_per_minute": 0,
            "unique_users": 0,
            "most_used_endpoints": []
        }
    
    @staticmethod
    async def _get_storage_metrics(db: AsyncSession) -> Dict[str, Any]:
        """Get storage consumption metrics"""
        storage_query = select(
            func.sum(Subscription.storage_used_mb).label("total_storage_mb"),
            func.avg(Subscription.storage_used_mb).label("avg_storage_mb"),
            func.max(Subscription.storage_used_mb).label("max_storage_mb")
        )
        storage_result = await db.execute(storage_query)
        storage_stats = storage_result.first()
        
        return {
            "total_mb": storage_stats.total_storage_mb or 0,
            "avg_mb_per_org": storage_stats.avg_storage_mb or 0,
            "max_mb_per_org": storage_stats.max_storage_mb or 0
        }
    
    @staticmethod
    async def _get_performance_metrics(db: AsyncSession) -> Dict[str, Any]:
        """Get performance metrics"""
        # This would require tracking performance data
        # For now, return placeholder data
        return {
            "avg_response_time_ms": 0,
            "p95_response_time_ms": 0,
            "p99_response_time_ms": 0,
            "error_rate": 0
        }
    
    @staticmethod
    async def _get_error_metrics(db: AsyncSession) -> Dict[str, Any]:
        """Get error rate metrics"""
        # This would require tracking errors in the database
        # For now, return placeholder data
        return {
            "total_errors": 0,
            "error_rate": 0,
            "most_common_errors": []
        }
    
    @staticmethod
    async def _get_database_metrics(db: AsyncSession) -> Dict[str, Any]:
        """Get database performance metrics"""
        # This would require database-specific monitoring
        # For now, return placeholder data
        return {
            "connection_count": 0,
            "query_count": 0,
            "avg_query_time_ms": 0,
            "slow_queries": 0
        }
    
    @staticmethod
    async def _get_user_activity_logs(db: AsyncSession) -> List[Dict[str, Any]]:
        """Get user activity logs"""
        # This would require tracking user activity in the database
        # For now, return placeholder data
        return []
    
    @staticmethod
    async def _get_support_metrics(db: AsyncSession) -> Dict[str, Any]:
        """Get support ticket metrics"""
        # This would require a support ticket system
        # For now, return placeholder data
        return {
            "total_tickets": 0,
            "open_tickets": 0,
            "avg_resolution_time_hours": 0,
            "satisfaction_score": 0
        }
    
    @staticmethod
    async def _get_satisfaction_metrics(db: AsyncSession) -> Dict[str, Any]:
        """Get customer satisfaction metrics"""
        # This would require tracking satisfaction data
        # For now, return placeholder data
        return {
            "nps_score": 0,
            "satisfaction_rate": 0,
            "feedback_count": 0
        }
    
    @staticmethod
    async def _get_usage_patterns(db: AsyncSession) -> Dict[str, Any]:
        """Get feature usage patterns"""
        # This would require tracking feature usage
        # For now, return placeholder data
        return {
            "most_used_features": [],
            "peak_usage_hours": [],
            "usage_by_day_of_week": {}
        }
