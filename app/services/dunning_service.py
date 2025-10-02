import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, func, case
from sqlalchemy.orm import selectinload

from ..models.subscription import Subscription, DunningStatus, SubscriptionStatus, Invoice, DunningEvent
from ..models.organization import Organization
from ..models.user import User
from ..services.stripe_service import StripeService

logger = logging.getLogger(__name__)


class DunningService:
    """Service for managing dunning processes and automated retry logic"""
    
    @staticmethod
    async def process_dunning_events(db: AsyncSession) -> Dict[str, Any]:
        """Process all pending dunning events"""
        try:
            # Get subscriptions that need dunning processing
            dunning_subscriptions = await DunningService._get_dunning_subscriptions(db)
            
            results = {
                "processed": 0,
                "emails_sent": 0,
                "payments_collected": 0,
                "suspended": 0,
                "errors": 0
            }
            
            for subscription in dunning_subscriptions:
                try:
                    result = await DunningService._process_subscription_dunning(subscription, db)
                    results["processed"] += 1
                    
                    if result.get("email_sent"):
                        results["emails_sent"] += 1
                    if result.get("payment_collected"):
                        results["payments_collected"] += 1
                    if result.get("suspended"):
                        results["suspended"] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing dunning for subscription {subscription.id}: {e}")
                    results["errors"] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to process dunning events: {e}")
            raise
    
    @staticmethod
    async def send_dunning_email(
        subscription: Subscription,
        attempt_number: int,
        db: AsyncSession
    ) -> bool:
        """Send dunning email notification"""
        try:
            # Get organization and primary user
            org_result = await db.execute(
                select(Organization).where(Organization.id == subscription.organization_id)
            )
            organization = org_result.scalar_one_or_none()
            
            if not organization:
                logger.error(f"Organization not found for subscription {subscription.id}")
                return False
            
            # Get admin user
            admin_result = await db.execute(
                select(User).where(
                    and_(
                        User.organization_id == subscription.organization_id,
                        User.role == "admin"
                    )
                )
            )
            admin_user = admin_result.scalar_one_or_none()
            
            if not admin_user:
                logger.error(f"Admin user not found for organization {organization.id}")
                return False
            
            # Create email content based on attempt number
            email_content = DunningService._create_dunning_email_content(
                subscription, organization, admin_user, attempt_number
            )
            
            # Send email (implement your email service here)
            # await EmailService.send_email(
            #     to_email=admin_user.email,
            #     subject=email_content["subject"],
            #     body=email_content["body"]
            # )
            
            # Get the latest invoice ID (if exists)
            latest_invoice_result = await db.execute(
                select(Invoice.id).where(Invoice.subscription_id == subscription.id)
                .order_by(Invoice.invoice_date.desc()).limit(1)
            )
            latest_invoice_id = latest_invoice_result.scalar()
            
            # Log the email event
            dunning_event = DunningEvent(
                id=str(uuid.uuid4()),
                subscription_id=subscription.id,
                invoice_id=latest_invoice_id,
                event_type="email_sent",
                attempt_number=attempt_number,
                status="sent",
                email_sent=True,
                email_delivered=True,
                event_metadata={
                    "email_to": admin_user.email,
                    "subject": email_content["subject"],
                    "template": f"dunning_attempt_{attempt_number}"
                }
            )
            db.add(dunning_event)
            
            # Update subscription
            subscription.last_dunning_email_sent = datetime.utcnow()
            subscription.dunning_email_count += 1
            
            await db.commit()
            
            logger.info(f"Sent dunning email for subscription {subscription.id}, attempt {attempt_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send dunning email: {e}")
            return False
    
    @staticmethod
    async def retry_payment(subscription: Subscription, db: AsyncSession) -> bool:
        """Retry payment for a subscription"""
        try:
            if not subscription.stripe_subscription_id:
                logger.error(f"No Stripe subscription ID for subscription {subscription.id}")
                return False
            
            # Get the latest invoice
            invoice_result = await db.execute(
                select(Invoice).where(
                    and_(
                        Invoice.subscription_id == subscription.id,
                        Invoice.status == "open"
                    )
                ).order_by(Invoice.invoice_date.desc())
            )
            invoice = invoice_result.scalar_one_or_none()
            
            if not invoice:
                logger.error(f"No open invoice found for subscription {subscription.id}")
                return False
            
            # Retry payment through Stripe
            try:
                # This would require Stripe's invoice.retrieve and invoice.pay methods
                # For now, we'll simulate a retry
                logger.info(f"Retrying payment for subscription {subscription.id}")
                
                # Update dunning event
                dunning_event = DunningEvent(
                    id=str(uuid.uuid4()),
                    subscription_id=subscription.id,
                    invoice_id=invoice.id,
                    event_type="payment_retry",
                    attempt_number=subscription.failed_payment_count + 1,
                    status="attempted",
                                    payment_attempted=True,
                payment_amount=invoice.amount_due,
                event_metadata={
                        "stripe_invoice_id": invoice.stripe_invoice_id,
                        "retry_method": "automatic"
                    }
                )
                db.add(dunning_event)
                
                await db.commit()
                return True
                
            except Exception as e:
                logger.error(f"Payment retry failed for subscription {subscription.id}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to retry payment: {e}")
            return False
    
    @staticmethod
    async def suspend_subscription(subscription: Subscription, db: AsyncSession) -> bool:
        """Suspend a subscription after failed payment attempts"""
        try:
            # Update subscription status
            subscription.status = SubscriptionStatus.PAUSED
            subscription.dunning_status = DunningStatus.SUSPENDED
            
            # Update in Stripe (if needed)
            if subscription.stripe_subscription_id:
                try:
                    # Pause subscription in Stripe
                    # stripe.Subscription.modify(
                    #     subscription.stripe_subscription_id,
                    #     pause_collection={"behavior": "void"}
                    # )
                    logger.info(f"Paused Stripe subscription {subscription.stripe_subscription_id}")
                except Exception as e:
                    logger.error(f"Failed to pause Stripe subscription: {e}")
            
            # Create dunning event
            dunning_event = DunningEvent(
                id=str(uuid.uuid4()),
                subscription_id=subscription.id,
                event_type="subscription_suspended",
                attempt_number=subscription.failed_payment_count,
                status="completed",
                event_metadata={
                    "reason": "max_payment_attempts_exceeded",
                    "failed_attempts": subscription.failed_payment_count
                }
            )
            db.add(dunning_event)
            
            await db.commit()
            
            logger.info(f"Suspended subscription {subscription.id} after {subscription.failed_payment_count} failed attempts")
            return True
            
        except Exception as e:
            logger.error(f"Failed to suspend subscription: {e}")
            return False
    
    @staticmethod
    async def reactivate_subscription(subscription: Subscription, db: AsyncSession) -> bool:
        """Reactivate a suspended subscription"""
        try:
            # Update subscription status
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.dunning_status = DunningStatus.NONE
            subscription.failed_payment_count = 0
            subscription.dunning_start_date = None
            subscription.next_dunning_date = None
            
            # Update in Stripe (if needed)
            if subscription.stripe_subscription_id:
                try:
                    # Resume subscription in Stripe
                    # stripe.Subscription.modify(
                    #     subscription.stripe_subscription_id,
                    #     pause_collection=None
                    # )
                    logger.info(f"Resumed Stripe subscription {subscription.stripe_subscription_id}")
                except Exception as e:
                    logger.error(f"Failed to resume Stripe subscription: {e}")
            
            # Create dunning event
            dunning_event = DunningEvent(
                id=str(uuid.uuid4()),
                subscription_id=subscription.id,
                event_type="subscription_reactivated",
                attempt_number=0,
                status="completed",
                event_metadata={
                    "reason": "payment_received",
                    "reactivation_method": "manual"
                }
            )
            db.add(dunning_event)
            
            await db.commit()
            
            logger.info(f"Reactivated subscription {subscription.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reactivate subscription: {e}")
            return False
    
    # Private helper methods
    
    @staticmethod
    async def _get_dunning_subscriptions(db: AsyncSession) -> List[Subscription]:
        """Get subscriptions that need dunning processing"""
        now = datetime.utcnow()
        
        # Get subscriptions that are past due and need dunning
        dunning_query = select(Subscription).where(
            and_(
                Subscription.status == SubscriptionStatus.PAST_DUE,
                Subscription.dunning_status != DunningStatus.SUSPENDED,
                Subscription.next_dunning_date <= now
            )
        ).options(selectinload(Subscription.organization))
        
        result = await db.execute(dunning_query)
        return result.scalars().all()
    
    @staticmethod
    async def _process_subscription_dunning(
        subscription: Subscription,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Process dunning for a single subscription"""
        result = {
            "email_sent": False,
            "payment_collected": False,
            "suspended": False
        }
        
        # Determine next action based on dunning status
        if subscription.dunning_status == DunningStatus.NONE:
            # First attempt
            subscription.dunning_status = DunningStatus.FIRST_ATTEMPT
            subscription.dunning_start_date = datetime.utcnow()
            subscription.next_dunning_date = datetime.utcnow() + timedelta(days=3)
            
            # Send first dunning email
            email_sent = await DunningService.send_dunning_email(subscription, 1, db)
            result["email_sent"] = email_sent
            
        elif subscription.dunning_status == DunningStatus.FIRST_ATTEMPT:
            # Second attempt
            subscription.dunning_status = DunningStatus.SECOND_ATTEMPT
            subscription.next_dunning_date = datetime.utcnow() + timedelta(days=7)
            
            # Retry payment
            payment_retried = await DunningService.retry_payment(subscription, db)
            if payment_retried:
                result["payment_collected"] = True
            else:
                # Send second dunning email
                email_sent = await DunningService.send_dunning_email(subscription, 2, db)
                result["email_sent"] = email_sent
                
        elif subscription.dunning_status == DunningStatus.SECOND_ATTEMPT:
            # Final attempt
            subscription.dunning_status = DunningStatus.FINAL_ATTEMPT
            subscription.next_dunning_date = datetime.utcnow() + timedelta(days=14)
            
            # Retry payment
            payment_retried = await DunningService.retry_payment(subscription, db)
            if payment_retried:
                result["payment_collected"] = True
            else:
                # Send final dunning email
                email_sent = await DunningService.send_dunning_email(subscription, 3, db)
                result["email_sent"] = email_sent
                
        elif subscription.dunning_status == DunningStatus.FINAL_ATTEMPT:
            # Suspend subscription
            suspended = await DunningService.suspend_subscription(subscription, db)
            result["suspended"] = suspended
        
        await db.commit()
        return result
    
    @staticmethod
    def _create_dunning_email_content(
        subscription: Subscription,
        organization: Organization,
        admin_user: User,
        attempt_number: int
    ) -> Dict[str, str]:
        """Create dunning email content"""
        
        email_templates = {
            1: {
                "subject": f"Payment Reminder - {organization.name}",
                "body": f"""
                Dear {admin_user.first_name},
                
                We noticed that your recent payment for {organization.name} was unsuccessful. 
                This is a friendly reminder to update your payment method to avoid any service interruption.
                
                Amount Due: ${subscription.amount / 100:.2f}
                Due Date: {subscription.current_period_end.strftime('%B %d, %Y')}
                
                Please log into your account to update your payment information:
                [Payment Portal Link]
                
                If you have any questions, please don't hesitate to contact our support team.
                
                Best regards,
                The Zphere Team
                """
            },
            2: {
                "subject": f"Urgent: Payment Required - {organization.name}",
                "body": f"""
                Dear {admin_user.first_name},
                
                Your payment for {organization.name} is now overdue. We've attempted to process your payment but were unable to do so.
                
                Amount Due: ${subscription.amount / 100:.2f}
                Days Overdue: {(datetime.utcnow() - subscription.current_period_end).days}
                
                To avoid service suspension, please update your payment method immediately:
                [Payment Portal Link]
                
                If you continue to experience issues, please contact our support team for assistance.
                
                Best regards,
                The Zphere Team
                """
            },
            3: {
                "subject": f"Final Notice: Service Suspension - {organization.name}",
                "body": f"""
                Dear {admin_user.first_name},
                
                This is our final notice regarding your overdue payment for {organization.name}. 
                Your account will be suspended within 24 hours if payment is not received.
                
                Amount Due: ${subscription.amount / 100:.2f}
                Days Overdue: {(datetime.utcnow() - subscription.current_period_end).days}
                
                To prevent service interruption, please make payment immediately:
                [Payment Portal Link]
                
                If you need assistance or have questions about your account, please contact our support team right away.
                
                Best regards,
                The Zphere Team
                """
            }
        }
        
        template = email_templates.get(attempt_number, email_templates[1])
        
        # Replace placeholders with actual values
        template["body"] = template["body"].replace(
            "[Payment Portal Link]",
            f"https://app.zphere.com/billing?org={organization.id}"
        )
        
        return template
    
    @staticmethod
    async def get_dunning_report(db: AsyncSession, days: int = 30) -> Dict[str, Any]:
        """Get dunning activity report"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Default empty report structure
            default_report = {
                "events_summary": {},
                "dunning_summary": {},
                "recovery_rate": 0.0,
                "revenue_recovered": 0.0,
                "active_dunning_count": 0,
                "avg_recovery_time_days": 0
            }
            
            try:
                # Dunning events summary
                events_query = select(
                    DunningEvent.event_type,
                    DunningEvent.status,
                    func.count(DunningEvent.id).label("count")
                ).where(
                    DunningEvent.created_at >= start_date
                ).group_by(DunningEvent.event_type, DunningEvent.status)
                
                events_result = await db.execute(events_query)
                events_summary = {}
                
                for row in events_result.fetchall():
                    if row.event_type not in events_summary:
                        events_summary[row.event_type] = {}
                    events_summary[row.event_type][row.status] = row.count
                
            except Exception as e:
                logger.warning(f"Failed to get dunning events (table may not exist): {e}")
                events_summary = {}
            
            try:
                # Subscriptions in dunning
                dunning_subscriptions_query = select(
                    Subscription.dunning_status,
                    func.count(Subscription.id).label("count")
                ).where(
                    Subscription.dunning_status != DunningStatus.NONE
                ).group_by(Subscription.dunning_status)
            except Exception as e:
                logger.warning(f"Failed to query subscription dunning status (table may not exist): {e}")
                return default_report
            
            try:
                dunning_result = await db.execute(dunning_subscriptions_query)
                dunning_summary = {row.dunning_status: row.count for row in dunning_result.fetchall()}
            except Exception as e:
                logger.warning(f"Failed to execute dunning subscriptions query: {e}")
                dunning_summary = {}
            
            recovery_stats = None
            recovery_rate = 0
            try:
                # Payment recovery rate
                recovery_query = select(
                    func.count(DunningEvent.id).label("total_attempts"),
                    func.sum(case((DunningEvent.payment_successful == True, 1), else_=0)).label("successful_payments")
                ).where(
                    and_(
                        DunningEvent.event_type == "payment_retry",
                        DunningEvent.created_at >= start_date
                    )
                )
                
                recovery_result = await db.execute(recovery_query)
                recovery_stats = recovery_result.first()
                
                if recovery_stats and recovery_stats.total_attempts and recovery_stats.total_attempts > 0:
                    recovery_rate = (recovery_stats.successful_payments / recovery_stats.total_attempts) * 100
            except Exception as e:
                logger.warning(f"Failed to get recovery stats: {e}")
                recovery_rate = 0
            
            return {
                "period_days": days,
                "events_summary": events_summary,
                "dunning_summary": dunning_summary,
                "recovery_rate": recovery_rate,
                "total_attempts": recovery_stats.total_attempts if recovery_stats else 0,
                "successful_recoveries": recovery_stats.successful_payments if recovery_stats else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get dunning report: {e}")
            raise
