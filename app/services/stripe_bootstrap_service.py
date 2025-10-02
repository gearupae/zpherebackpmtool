import os
import stripe
from typing import Optional
from ..core.config import settings

# Names for products/prices we will create if missing
CORE_PRODUCT_NAME = "Zphere Pro (no AI)"
AI_PRODUCT_NAME = "Zphere Pro + AI"

CORE_PRICE_NICK = "pro_core_monthly_9usd"
AI_PRICE_NICK = "pro_ai_monthly_18usd"


def _set_env_price_ids(core_price_id: str, ai_price_id: str) -> None:
    # Set for current process so endpoints can read immediately
    if core_price_id:
        os.environ["STRIPE_PRICE_CORE_MONTHLY"] = core_price_id
    if ai_price_id:
        os.environ["STRIPE_PRICE_AI_MONTHLY"] = ai_price_id


def _find_or_create_product(name: str) -> Optional[str]:
    try:
        prods = stripe.Product.list(limit=50)
        for p in prods.data:
            if p.name == name:
                return p.id
        # Create if not found
        created = stripe.Product.create(name=name)
        return created.id
    except Exception:
        return None


def _find_price_by_nickname(nickname: str) -> Optional[str]:
    try:
        prices = stripe.Price.list(limit=50)
        for pr in prices.data:
            if pr.nickname == nickname:
                return pr.id
        return None
    except Exception:
        return None


def _find_or_create_monthly_price(product_id: str, unit_amount_cents: int, nickname: str) -> Optional[str]:
    # Try by nickname first
    ex = _find_price_by_nickname(nickname)
    if ex:
        return ex
    try:
        pr = stripe.Price.create(
            unit_amount=unit_amount_cents,
            currency="usd",
            recurring={"interval": "month"},
            product=product_id,
            nickname=nickname,
        )
        return pr.id
    except Exception:
        return None


def ensure_stripe_prices() -> None:
    """Best-effort creation of Stripe products and monthly prices for $9 and $18.
    Sets STRIPE_PRICE_CORE_MONTHLY and STRIPE_PRICE_AI_MONTHLY in-process if created.
    Safe to run multiple times.
    """
    # Require secret key
    if not settings.STRIPE_SECRET_KEY:
        return
    stripe.api_key = settings.STRIPE_SECRET_KEY

    core_env = os.getenv("STRIPE_PRICE_CORE_MONTHLY")
    ai_env = os.getenv("STRIPE_PRICE_AI_MONTHLY")
    if core_env and ai_env:
        # Already configured
        return

    try:
        core_pid = _find_or_create_product(CORE_PRODUCT_NAME)
        ai_pid = _find_or_create_product(AI_PRODUCT_NAME)
        core_price_id = core_env or (core_pid and _find_or_create_monthly_price(core_pid, 900, CORE_PRICE_NICK))
        ai_price_id = ai_env or (ai_pid and _find_or_create_monthly_price(ai_pid, 1800, AI_PRICE_NICK))
        if core_price_id and ai_price_id:
            _set_env_price_ids(core_price_id, ai_price_id)
    except Exception:
        # Non-fatal; do nothing
        pass
