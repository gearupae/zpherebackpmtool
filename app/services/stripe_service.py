import stripe
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
import uuid

from ..core.config import settings
from ..models.subscription import Subscription, Invoice, DunningEvent, SubscriptionStatus, DunningStatus
from ..models.organization import Organization
from ..models.user import User

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class StripeService:
    """Service for handling Stripe operations"""
    
    @staticmethod
    async def create_customer(user: User, organization: Organization) -> str:
        """Create a Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}",
                metadata={
                    "organization_id": organization.id,
                    "user_id": user.id,
                    "organization_name": organization.name
                }
            )
            return customer.id
        except Exception as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise
    
    @staticmethod
    async def create_subscription(
        customer_id: str,
        price_id: str,
        trial_days: int = 14
    ) -> Dict[str, Any]:
        """Create a Stripe subscription"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                trial_period_days=trial_days,
                payment_behavior="default_incomplete",
                payment_settings={"save_default_payment_method": "on_subscription"},
                expand=["latest_invoice.payment_intent"]
            )
            return subscription
        except Exception as e:
            logger.error(f"Failed to create Stripe subscription: {e}")
            raise
    
    @staticmethod
    async def update_subscription(
        subscription_id: str,
        price_id: str,
        proration_behavior: str = "create_prorations"
    ) -> Dict[str, Any]:
        """Update a Stripe subscription"""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                items=[{"price": price_id}],
                proration_behavior=proration_behavior
            )
            return subscription
        except Exception as e:
            logger.error(f"Failed to update Stripe subscription: {e}")
            raise
    
    @staticmethod
    async def cancel_subscription(
        subscription_id: str,
        cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel a Stripe subscription"""
        try:
            if cancel_at_period_end:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                subscription = stripe.Subscription.delete(subscription_id)
            return subscription
        except Exception as e:
            logger.error(f"Failed to cancel Stripe subscription: {e}")
            raise
    
    @staticmethod
    async def create_payment_method(
        type: str,
        card: Optional[Dict[str, Any]] = None,
        billing_details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a payment method"""
        try:
            payment_method_data = {"type": type}
            if card:
                payment_method_data["card"] = card
            if billing_details:
                payment_method_data["billing_details"] = billing_details
            
            payment_method = stripe.PaymentMethod.create(**payment_method_data)
            return payment_method.id
        except Exception as e:
            logger.error(f"Failed to create payment method: {e}")
            raise
    
    @staticmethod
    async def attach_payment_method_to_customer(
        payment_method_id: str,
        customer_id: str
    ) -> None:
        """Attach payment method to customer"""
        try:
            stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)
        except Exception as e:
            logger.error(f"Failed to attach payment method: {e}")
            raise
    
    @staticmethod
    async def create_invoice(
        customer_id: str,
        subscription_id: str,
        amount: int,
        currency: str = "usd",
        description: str = ""
    ) -> Dict[str, Any]:
        """Create a Stripe invoice"""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                subscription=subscription_id,
                amount=amount,
                currency=currency,
                description=description
            )
            return invoice
        except Exception as e:
            logger.error(f"Failed to create Stripe invoice: {e}")
            raise
    
    @staticmethod
    async def process_webhook(
        payload: bytes,
        sig_header: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            
            # Handle the event
            if event['type'] == 'customer.subscription.created':
                await StripeService._handle_subscription_created(event, db)
            elif event['type'] == 'customer.subscription.updated':
                await StripeService._handle_subscription_updated(event, db)
            elif event['type'] == 'customer.subscription.deleted':
                await StripeService._handle_subscription_deleted(event, db)
            elif event['type'] == 'invoice.payment_succeeded':
                await StripeService._handle_payment_succeeded(event, db)
            elif event['type'] == 'invoice.payment_failed':
                await StripeService._handle_payment_failed(event, db)
            elif event['type'] == 'invoice.payment_action_required':
                await StripeService._handle_payment_action_required(event, db)
            elif event['type'] == 'customer.subscription.trial_will_end':
                await StripeService._handle_trial_will_end(event, db)
            
            return {"status": "success", "event_type": event['type']}
            
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            raise
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            raise
    
    @staticmethod
    async def _handle_subscription_created(event: Dict[str, Any], db: AsyncSession):
        """Handle subscription.created event"""
        subscription_data = event['data']['object']
        organization_id = subscription_data['metadata'].get('organization_id')
        
        if not organization_id:
            logger.error("No organization_id in subscription metadata")
            return
        
        # Update local subscription
        result = await db.execute(
            select(Subscription).where(Subscription.organization_id == organization_id)
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            subscription.stripe_subscription_id = subscription_data['id']
            subscription.stripe_customer_id = subscription_data['customer']
            subscription.status = SubscriptionStatus(subscription_data['status'])
            subscription.current_period_start = datetime.fromtimestamp(subscription_data['current_period_start'])
            subscription.current_period_end = datetime.fromtimestamp(subscription_data['current_period_end'])
            
            if subscription_data.get('trial_start'):
                subscription.trial_start = datetime.fromtimestamp(subscription_data['trial_start'])
            if subscription_data.get('trial_end'):
                subscription.trial_end = datetime.fromtimestamp(subscription_data['trial_end'])
            
            await db.commit()
            logger.info(f"Updated subscription {subscription_data['id']} for organization {organization_id}")
    
    @staticmethod
    async def _handle_subscription_updated(event: Dict[str, Any], db: AsyncSession):
        """Handle subscription.updated event"""
        subscription_data = event['data']['object']
        organization_id = subscription_data['metadata'].get('organization_id')
        
        if not organization_id:
            logger.error("No organization_id in subscription metadata")
            return
        
        # Update local subscription
        result = await db.execute(
            select(Subscription).where(Subscription.organization_id == organization_id)
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            subscription.status = SubscriptionStatus(subscription_data['status'])
            subscription.current_period_start = datetime.fromtimestamp(subscription_data['current_period_start'])
            subscription.current_period_end = datetime.fromtimestamp(subscription_data['current_period_end'])
            subscription.cancel_at_period_end = subscription_data.get('cancel_at_period_end', False)
            
            if subscription_data.get('canceled_at'):
                subscription.cancelled_at = datetime.fromtimestamp(subscription_data['canceled_at'])
            
            await db.commit()
            logger.info(f"Updated subscription {subscription_data['id']} for organization {organization_id}")
    
    @staticmethod
    async def _handle_subscription_deleted(event: Dict[str, Any], db: AsyncSession):
        """Handle subscription.deleted event"""
        subscription_data = event['data']['object']
        organization_id = subscription_data['metadata'].get('organization_id')
        
        if not organization_id:
            logger.error("No organization_id in subscription metadata")
            return
        
        # Update local subscription
        result = await db.execute(
            select(Subscription).where(Subscription.organization_id == organization_id)
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.cancelled_at = datetime.utcnow()
            await db.commit()
            logger.info(f"Cancelled subscription {subscription_data['id']} for organization {organization_id}")
    
    @staticmethod
    async def _handle_payment_succeeded(event: Dict[str, Any], db: AsyncSession):
        """Handle invoice.payment_succeeded event"""
        invoice_data = event['data']['object']
        subscription_id = invoice_data.get('subscription')
        
        if not subscription_id:
            return
        
        # Find subscription
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            # Update subscription
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.last_payment_date = datetime.utcnow()
            subscription.failed_payment_count = 0
            subscription.dunning_status = DunningStatus.NONE
            
            # Create or update invoice
            invoice_result = await db.execute(
                select(Invoice).where(Invoice.stripe_invoice_id == invoice_data['id'])
            )
            invoice = invoice_result.scalar_one_or_none()
            
            if not invoice:
                invoice = Invoice(
                    id=str(uuid.uuid4()),
                    subscription_id=subscription.id,
                    stripe_invoice_id=invoice_data['id'],
                    amount_paid=invoice_data['amount_paid'],
                    amount_due=invoice_data['amount_due'],
                    currency=invoice_data['currency'],
                    status=invoice_data['status'],
                    invoice_date=datetime.fromtimestamp(invoice_data['created']),
                    paid_date=datetime.utcnow(),
                    invoice_number=invoice_data.get('number'),
                    description=invoice_data.get('description', '')
                )
                db.add(invoice)
            else:
                invoice.status = invoice_data['status']
                invoice.amount_paid = invoice_data['amount_paid']
                invoice.paid_date = datetime.utcnow()
            
            await db.commit()
            logger.info(f"Payment succeeded for subscription {subscription_id}")
    
    @staticmethod
    async def _handle_payment_failed(event: Dict[str, Any], db: AsyncSession):
        """Handle invoice.payment_failed event"""
        invoice_data = event['data']['object']
        subscription_id = invoice_data.get('subscription')
        
        if not subscription_id:
            return
        
        # Find subscription
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            # Update subscription
            subscription.status = SubscriptionStatus.PAST_DUE
            subscription.failed_payment_count += 1
            
            # Update dunning status
            if subscription.failed_payment_count == 1:
                subscription.dunning_status = DunningStatus.FIRST_ATTEMPT
                subscription.dunning_start_date = datetime.utcnow()
                subscription.next_dunning_date = datetime.utcnow() + timedelta(days=3)
            elif subscription.failed_payment_count == 2:
                subscription.dunning_status = DunningStatus.SECOND_ATTEMPT
                subscription.next_dunning_date = datetime.utcnow() + timedelta(days=7)
            elif subscription.failed_payment_count >= 3:
                subscription.dunning_status = DunningStatus.FINAL_ATTEMPT
                subscription.next_dunning_date = datetime.utcnow() + timedelta(days=14)
            
            await db.commit()
            logger.info(f"Payment failed for subscription {subscription_id}, attempt {subscription.failed_payment_count}")
    
    @staticmethod
    async def _handle_payment_action_required(event: Dict[str, Any], db: AsyncSession):
        """Handle invoice.payment_action_required event"""
        invoice_data = event['data']['object']
        subscription_id = invoice_data.get('subscription')
        
        if not subscription_id:
            return
        
        # Find subscription
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            subscription.status = SubscriptionStatus.INCOMPLETE
            await db.commit()
            logger.info(f"Payment action required for subscription {subscription_id}")
    
    @staticmethod
    async def _handle_trial_will_end(event: Dict[str, Any], db: AsyncSession):
        """Handle customer.subscription.trial_will_end event"""
        subscription_data = event['data']['object']
        organization_id = subscription_data['metadata'].get('organization_id')
        
        if not organization_id:
            logger.error("No organization_id in subscription metadata")
            return
        
        # Send trial ending notification
        logger.info(f"Trial ending for organization {organization_id}")
        # TODO: Send email notification
    
    @staticmethod
    async def get_subscription_usage(subscription_id: str) -> Dict[str, Any]:
        """Get subscription usage data"""
        try:
            usage = stripe.Subscription.retrieve(subscription_id)
            return {
                "subscription_id": usage.id,
                "status": usage.status,
                "current_period_start": usage.current_period_start,
                "current_period_end": usage.current_period_end,
                "trial_end": usage.trial_end,
                "cancel_at_period_end": usage.cancel_at_period_end,
                "items": [
                    {
                        "price_id": item.price.id,
                        "quantity": item.quantity,
                        "unit_amount": item.price.unit_amount,
                        "currency": item.price.currency
                    }
                    for item in usage.items.data
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get subscription usage: {e}")
            raise
    
    @staticmethod
    async def create_checkout_session(
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        trial_days: int = 14
    ) -> str:
        """Create a Stripe checkout session"""
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                trial_period_days=trial_days,
                allow_promotion_codes=True,
                billing_address_collection='required',
                metadata={
                    'customer_id': customer_id,
                    'price_id': price_id
                }
            )
            return session.id
        except Exception as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise
    
    @staticmethod
    async def create_portal_session(customer_id: str, return_url: str) -> str:
        """Create a Stripe customer portal session"""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            return session.url
        except Exception as e:
            logger.error(f"Failed to create portal session: {e}")
            raise
