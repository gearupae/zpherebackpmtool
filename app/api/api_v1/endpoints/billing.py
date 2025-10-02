from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import stripe
import os
from datetime import datetime
from typing import Tuple

from ....core.config import settings
from ....db.database import get_db
from ....models.subscription import Subscription as SubscriptionModel, SubscriptionStatus, SubscriptionTier
from ....models.organization import Organization
from ....models.user import User
from ...deps import get_current_active_user, get_current_organization

router = APIRouter()

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Helper to read price IDs at request time (allows runtime bootstrap to populate)
def _get_price_ids() -> Tuple[str, str]:
    return os.getenv("STRIPE_PRICE_CORE_MONTHLY", ""), os.getenv("STRIPE_PRICE_AI_MONTHLY", "")

PUBLISHABLE_KEY = settings.STRIPE_PUBLISHABLE_KEY


def _get_success_cancel_urls(request: Request) -> tuple[str, str]:
    origin = request.headers.get("origin") or "http://localhost:3001"
    success_url = f"{origin}/billing?status=success"
    cancel_url = f"{origin}/billing?status=cancel"
    return success_url, cancel_url


@router.get("/config")
async def get_public_config() -> Any:
    """Expose publishable key to the frontend."""
    c, a = _get_price_ids()
    return {"publishableKey": PUBLISHABLE_KEY, "hasPrices": bool(c and a)}


@router.post("/activate-free")
async def activate_free_plan(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Activate Starter (free) tier for current organization."""
    result = await db.execute(
        select(SubscriptionModel).where(SubscriptionModel.organization_id == current_org.id)
    )
    subscription = result.scalar_one_or_none()

    if subscription is None:
        subscription = SubscriptionModel(
            organization_id=current_org.id,
            stripe_subscription_id="",
            stripe_customer_id="",
            stripe_price_id="",
            tier=SubscriptionTier.STARTER,
            status=SubscriptionStatus.ACTIVE,
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
            cancel_at_period_end=False,
        )
        db.add(subscription)
    else:
        subscription.tier = SubscriptionTier.STARTER
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.amount = 0
        subscription.stripe_subscription_id = subscription.stripe_subscription_id or ""
        subscription.stripe_price_id = ""

    await db.commit()
    await db.refresh(subscription)
    return {"message": "Free plan activated", "subscription": {
        "tier": subscription.tier, "status": subscription.status
    }}


@router.post("/checkout-session")
async def create_checkout_session(
    request: Request,
    body: dict,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a Stripe Checkout session for subscription.
    body: { "tier": "pro_core" | "pro_ai" }
    """
    tier = body.get("tier")
    if tier not in ("pro_core", "pro_ai"):
        raise HTTPException(status_code=400, detail="Invalid tier")

    c_price, a_price = _get_price_ids()
    price_id = c_price if tier == "pro_core" else a_price
    if not price_id:
        raise HTTPException(status_code=400, detail="Price ID not configured")

    success_url, cancel_url = _get_success_cancel_urls(request)

    # Ensure Stripe customer via checkout session (set customer_email)
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=current_user.email,
            metadata={"organization_id": current_org.id, "user_id": current_user.id, "tier": tier},
            subscription_data={
                "metadata": {"organization_id": current_org.id, "tier": tier}
            },
            success_url=success_url + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            allow_promotion_codes=True,
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")


@router.post("/portal-session")
async def create_portal_session(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a Stripe Billing Portal session for the current organization."""
    result = await db.execute(
        select(SubscriptionModel).where(SubscriptionModel.organization_id == current_org.id)
    )
    subscription = result.scalar_one_or_none()
    if not subscription or not subscription.stripe_customer_id:
        raise HTTPException(status_code=404, detail="No Stripe customer for this organization")

    origin = request.headers.get("origin") or "http://localhost:3001"
    try:
        portal = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=f"{origin}/billing"
        )
        return {"url": portal.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")
