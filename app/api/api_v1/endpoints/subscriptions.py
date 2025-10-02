from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import stripe
import uuid
from datetime import datetime

from ....db.database import get_db
from ....models.subscription import Subscription as SubscriptionModel, SubscriptionStatus, SubscriptionTier
from ....models.organization import Organization
from ....models.user import User
from ....core.config import settings
from ...deps import get_current_active_user, require_admin, get_current_organization

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter()


@router.get("/")
async def get_subscription(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get current organization's subscription"""
    
    result = await db.execute(
        select(SubscriptionModel).where(
            SubscriptionModel.organization_id == current_org.id
        )
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        # Create default starter subscription
        subscription = SubscriptionModel(
            id=str(uuid.uuid4()),
            organization_id=current_org.id,
            stripe_subscription_id="",
            stripe_customer_id="",
            stripe_price_id="",
            tier=SubscriptionTier.STARTER,
            status=SubscriptionStatus.TRIALING,
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
            amount=0,
            currency="usd",
            interval="month",
            user_count=1,
            project_count=0,
            storage_used_mb=0,
            features={},
            failed_payment_count=0,
            cancel_at_period_end=False
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
    
    return subscription


@router.get("/stats")
async def get_subscription_stats(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get subscription usage statistics"""
    
    subscription_result = await db.execute(
        select(SubscriptionModel).where(
            SubscriptionModel.organization_id == current_org.id
        )
    )
    subscription = subscription_result.scalar_one_or_none()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found"
        )
    
    # Get usage counts
    from ....models.user import User as UserModel
    from ....models.project import Project
    
    user_count_result = await db.execute(
        select(func.count()).where(UserModel.organization_id == current_org.id)
    )
    user_count = user_count_result.scalar()
    
    project_count_result = await db.execute(
        select(func.count()).where(Project.organization_id == current_org.id)
    )
    project_count = project_count_result.scalar()
    
    return {
        "tier": subscription.tier,
        "status": subscription.status,
        "user_count": user_count,
        "project_count": project_count,
        "amount": subscription.amount,
        "currency": subscription.currency,
        "cancel_at_period_end": subscription.cancel_at_period_end
    }


@router.post("/create")
async def create_subscription(
    subscription_data: dict,
    current_user: User = Depends(require_admin),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new Stripe subscription"""
    
    try:
        # Create Stripe customer
        stripe_customer = stripe.Customer.create(
            email=current_user.email,
            name=f"{current_user.first_name} {current_user.last_name}",
            metadata={"organization_id": current_org.id}
        )
        
        # Create Stripe subscription
        stripe_subscription = stripe.Subscription.create(
            customer=stripe_customer.id,
            items=[{"price": subscription_data["stripe_price_id"]}],
        )
        
        # Create local subscription
        subscription = SubscriptionModel(
            id=str(uuid.uuid4()),
            organization_id=current_org.id,
            stripe_subscription_id=stripe_subscription.id,
            stripe_customer_id=stripe_customer.id,
            stripe_price_id=subscription_data["stripe_price_id"],
            tier=SubscriptionTier(subscription_data["tier"]),
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
            current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
            amount=stripe_subscription.items.data[0].price.unit_amount,
            currency=stripe_subscription.items.data[0].price.currency,
            interval=stripe_subscription.items.data[0].price.recurring.interval,
            user_count=1,
            project_count=0,
            storage_used_mb=0,
            features={},
            failed_payment_count=0,
            cancel_at_period_end=False
        )
        db.add(subscription)
        await db.commit()
        
        return {"message": "Subscription created successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create subscription: {str(e)}"
        )


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(require_admin),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Cancel subscription"""
    
    result = await db.execute(
        select(SubscriptionModel).where(
            SubscriptionModel.organization_id == current_org.id
        )
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found"
        )
    
    subscription.status = SubscriptionStatus.CANCELLED
    subscription.cancelled_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "Subscription cancelled"}


@router.get("/invoices")
async def get_subscription_invoices(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get subscription invoices"""
    return {"invoices": []}


@router.post("/webhooks")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Handle Stripe webhooks"""
    try:
        # Get the raw body
        body = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        if not sig_header:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing stripe-signature header"
            )
        
        # Process the webhook
        from ....services.stripe_service import StripeService
        result = await StripeService.process_webhook(body, sig_header, db)
        
        return result
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook processing failed: {str(e)}"
        )
