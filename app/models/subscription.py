from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Integer, JSON, Enum, Text
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
    PAUSED = "paused"


class SubscriptionTier(str, enum.Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class DunningStatus(str, enum.Enum):
    NONE = "none"
    FIRST_ATTEMPT = "first_attempt"
    SECOND_ATTEMPT = "second_attempt"
    FINAL_ATTEMPT = "final_attempt"
    SUSPENDED = "suspended"


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
    
    # Dunning management
    dunning_status = Column(Enum(DunningStatus), default=DunningStatus.NONE)
    dunning_start_date = Column(DateTime(timezone=True))
    last_dunning_email_sent = Column(DateTime(timezone=True))
    dunning_email_count = Column(Integer, default=0)
    next_dunning_date = Column(DateTime(timezone=True))
    
    # Payment method
    payment_method_id = Column(String(100))
    payment_method_type = Column(String(50))  # card, bank_account, etc.
    payment_method_last4 = Column(String(4))
    payment_method_brand = Column(String(20))  # visa, mastercard, etc.
    
    # Cancellation
    cancel_at_period_end = Column(Boolean, default=False)
    cancelled_at = Column(DateTime(timezone=True))
    cancellation_reason = Column(Text)
    
    # Proration and changes
    proration_date = Column(DateTime(timezone=True))
    pending_changes = Column(JSON, default=dict)
    
    # Analytics and tracking
    total_paid = Column(Integer, default=0)  # Total amount paid in cents
    lifetime_value = Column(Integer, default=0)  # Total value in cents
    churn_risk_score = Column(Integer, default=0)  # 0-100 risk score
    last_activity_date = Column(DateTime(timezone=True))
    
    # Relationships
    organization = relationship("Organization", back_populates="subscription")
    invoices = relationship("Invoice", back_populates="subscription")
    
    @property
    def is_active(self):
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
    
    @property
    def is_trial(self):
        return self.status == SubscriptionStatus.TRIALING
    
    @property
    def is_past_due(self):
        return self.status == SubscriptionStatus.PAST_DUE
    
    @property
    def is_cancelled(self):
        return self.status == SubscriptionStatus.CANCELLED
    
    @property
    def days_until_renewal(self):
        """Calculate days until next renewal"""
        from datetime import datetime
        if not self.current_period_end:
            return 0
        delta = self.current_period_end - datetime.utcnow()
        return max(0, delta.days)
    
    @property
    def trial_days_remaining(self):
        """Calculate remaining trial days"""
        from datetime import datetime
        if not self.is_trial or not self.trial_end:
            return 0
        delta = self.trial_end - datetime.utcnow()
        return max(0, delta.days)
    
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
                "api_access": False,
                "white_label": False,
                "sso": False,
                "audit_logs": False,
                "custom_workflows": False,
            },
            SubscriptionTier.PROFESSIONAL: {
                "max_users": 15,
                "max_projects": 25,
                "max_storage_gb": 10,
                "integrations": True,
                "advanced_analytics": True,
                "custom_branding": False,
                "priority_support": False,
                "api_access": True,
                "white_label": False,
                "sso": False,
                "audit_logs": False,
                "custom_workflows": False,
            },
            SubscriptionTier.BUSINESS: {
                "max_users": 50,
                "max_projects": -1,  # Unlimited
                "max_storage_gb": 100,
                "integrations": True,
                "advanced_analytics": True,
                "custom_branding": True,
                "priority_support": True,
                "api_access": True,
                "white_label": False,
                "sso": True,
                "audit_logs": True,
                "custom_workflows": True,
            },
            SubscriptionTier.ENTERPRISE: {
                "max_users": -1,  # Unlimited
                "max_projects": -1,  # Unlimited
                "max_storage_gb": -1,  # Unlimited
                "integrations": True,
                "advanced_analytics": True,
                "custom_branding": True,
                "priority_support": True,
                "api_access": True,
                "white_label": True,
                "sso": True,
                "audit_logs": True,
                "custom_workflows": True,
            }
        }
        return limits.get(self.tier, limits[SubscriptionTier.STARTER])
    
    def has_feature(self, feature_name: str) -> bool:
        """Check if subscription has access to a specific feature"""
        limits = self.get_feature_limits()
        return limits.get(feature_name, False)
    
    def get_usage_percentage(self, resource_type: str) -> float:
        """Get usage percentage for a resource type"""
        limits = self.get_feature_limits()
        limit_key = f"max_{resource_type}"
        
        if limit_key not in limits:
            return 0.0
        
        limit = limits[limit_key]
        if limit == -1:  # Unlimited
            return 0.0
        
        current_usage = getattr(self, f"{resource_type}_count", 0)
        return min(100.0, (current_usage / limit) * 100) if limit > 0 else 0.0
    
    def is_over_limit(self, resource_type: str) -> bool:
        """Check if usage is over the limit for a resource type"""
        limits = self.get_feature_limits()
        limit_key = f"max_{resource_type}"
        
        if limit_key not in limits:
            return False
        
        limit = limits[limit_key]
        if limit == -1:  # Unlimited
            return False
        
        current_usage = getattr(self, f"{resource_type}_count", 0)
        return current_usage > limit
    
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
    
    # Payment tracking
    payment_intent_id = Column(String(100))
    payment_method_id = Column(String(100))
    payment_method_type = Column(String(50))
    payment_method_last4 = Column(String(4))
    
    # Dunning information
    dunning_attempt = Column(Integer, default=0)
    last_dunning_email = Column(DateTime(timezone=True))
    
    # Relationships
    subscription = relationship("Subscription", back_populates="invoices")
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        from datetime import datetime
        if not self.due_date or self.status == "paid":
            return False
        return datetime.utcnow() > self.due_date
    
    @property
    def days_overdue(self):
        """Get days overdue"""
        from datetime import datetime
        if not self.is_overdue:
            return 0
        return (datetime.utcnow() - self.due_date).days
    
    def __repr__(self):
        return f"<Invoice(invoice_number='{self.invoice_number}', status='{self.status}')>"


class DunningEvent(UUIDBaseModel):
    """Dunning event tracking"""
    __tablename__ = "dunning_events"
    
    subscription_id = Column(String, ForeignKey("subscriptions.id"), nullable=False)
    invoice_id = Column(String, ForeignKey("invoices.id"), nullable=False)
    
    # Event details
    event_type = Column(String(50), nullable=False)  # email_sent, payment_attempt, etc.
    attempt_number = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)  # sent, delivered, failed, etc.
    
    # Communication details
    email_sent = Column(Boolean, default=False)
    email_delivered = Column(Boolean, default=False)
    email_opened = Column(Boolean, default=False)
    email_clicked = Column(Boolean, default=False)
    
    # Payment attempt
    payment_attempted = Column(Boolean, default=False)
    payment_successful = Column(Boolean, default=False)
    payment_amount = Column(Integer, default=0)
    
    # Event metadata
    event_metadata = Column(JSON, default=dict)
    
    # Relationships
    subscription = relationship("Subscription")
    invoice = relationship("Invoice")
    
    def __repr__(self):
        return f"<DunningEvent(type='{self.event_type}', attempt={self.attempt_number})>"
