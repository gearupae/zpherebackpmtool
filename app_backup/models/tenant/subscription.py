from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Integer, JSON, Enum
from sqlalchemy.orm import relationship
import enum
from .base import UUIDBaseModel


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    UNPAID = "unpaid"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"


class SubscriptionTier(str, enum.Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class Subscription(UUIDBaseModel):
    """Subscription model for Stripe integration"""
    __tablename__ = "subscriptions"
    
    # Organization relationship
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Stripe identifiers
    stripe_subscription_id = Column(String(100), unique=True, nullable=False)
    stripe_customer_id = Column(String(100), nullable=False)
    stripe_price_id = Column(String(100), nullable=False)
    
    # Subscription details
    tier = Column(Enum(SubscriptionTier), nullable=False)  # starter, professional, business, enterprise
    status = Column(Enum(SubscriptionStatus), nullable=False)
    
    # Billing information
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    trial_start = Column(DateTime(timezone=True))
    trial_end = Column(DateTime(timezone=True))
    
    # Pricing
    amount = Column(Integer, nullable=False)  # Amount in cents
    currency = Column(String(3), default="usd")
    interval = Column(String(20), default="month")  # month, year
    
    # Usage and limits
    user_count = Column(Integer, default=0)
    project_count = Column(Integer, default=0)
    storage_used_mb = Column(Integer, default=0)
    
    # Feature flags based on subscription tier
    features = Column(JSON, default=dict)
    
    # Billing history
    last_payment_date = Column(DateTime(timezone=True))
    next_payment_date = Column(DateTime(timezone=True))
    failed_payment_count = Column(Integer, default=0)
    
    # Cancellation
    cancel_at_period_end = Column(Boolean, default=False)
    cancelled_at = Column(DateTime(timezone=True))
    
    # Relationships
    organization = relationship("Organization", back_populates="subscription")
    invoices = relationship("Invoice", back_populates="subscription")
    
    @property
    def is_active(self):
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
    
    @property
    def is_trial(self):
        return self.status == SubscriptionStatus.TRIALING
    
    def get_feature_limits(self):
        """Get feature limits based on subscription tier"""
        limits = {
            SubscriptionTier.STARTER: {
                "max_users": 3,
                "max_projects": 5,
                "max_storage_gb": 1,
                "integrations": False,
                "advanced_analytics": False,
                "custom_branding": False,
                "priority_support": False,
            },
            SubscriptionTier.PROFESSIONAL: {
                "max_users": 15,
                "max_projects": 25,
                "max_storage_gb": 10,
                "integrations": True,
                "advanced_analytics": True,
                "custom_branding": False,
                "priority_support": False,
            },
            SubscriptionTier.BUSINESS: {
                "max_users": 50,
                "max_projects": -1,  # Unlimited
                "max_storage_gb": 100,
                "integrations": True,
                "advanced_analytics": True,
                "custom_branding": True,
                "priority_support": True,
            },
            SubscriptionTier.ENTERPRISE: {
                "max_users": -1,  # Unlimited
                "max_projects": -1,  # Unlimited
                "max_storage_gb": -1,  # Unlimited
                "integrations": True,
                "advanced_analytics": True,
                "custom_branding": True,
                "priority_support": True,
            }
        }
        return limits.get(self.tier, limits[SubscriptionTier.STARTER])
    
    def __repr__(self):
        return f"<Subscription(tier='{self.tier}', status='{self.status}')>"


class Invoice(UUIDBaseModel):
    """Invoice model for billing history"""
    __tablename__ = "invoices"
    
    subscription_id = Column(String, ForeignKey("subscriptions.id"), nullable=False)
    stripe_invoice_id = Column(String(100), unique=True, nullable=False)
    
    # Invoice details
    amount_paid = Column(Integer, nullable=False)  # Amount in cents
    amount_due = Column(Integer, nullable=False)
    currency = Column(String(3), default="usd")
    status = Column(String(50), nullable=False)  # paid, open, void, uncollectible
    
    # Dates
    invoice_date = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(DateTime(timezone=True))
    paid_date = Column(DateTime(timezone=True))
    
    # Invoice details
    invoice_number = Column(String(100))
    description = Column(String(500))
    
    # Relationships
    subscription = relationship("Subscription", back_populates="invoices")
    
    def __repr__(self):
        return f"<Invoice(invoice_number='{self.invoice_number}', status='{self.status}')>"
