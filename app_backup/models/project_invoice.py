from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime, JSON, Integer, Enum
from sqlalchemy.orm import relationship
import enum
from .base import UUIDBaseModel


class InvoiceStatus(str, enum.Enum):
    """Invoice payment status"""
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    PARTIALLY_PAID = "partially_paid"
    CANCELLED = "cancelled"
    VOID = "void"


class InvoiceType(str, enum.Enum):
    """Types of invoices"""
    PROJECT = "project"
    RECURRING = "recurring"
    TIME_AND_MATERIALS = "time_and_materials"
    FIXED_PRICE = "fixed_price"
    HOURLY = "hourly"
    EXPENSE = "expense"


class ProjectInvoice(UUIDBaseModel):
    """Project-based invoice model"""
    __tablename__ = "project_invoices"
    
    # Basic invoice info
    invoice_number = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Organization and relationships
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Invoice details
    invoice_type = Column(Enum(InvoiceType), default=InvoiceType.PROJECT)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)
    
    # Financial information
    subtotal = Column(Integer, default=0)  # Amount before tax in cents
    tax_amount = Column(Integer, default=0)  # Tax amount in cents
    discount_amount = Column(Integer, default=0)  # Discount amount in cents
    total_amount = Column(Integer, default=0)  # Total amount in cents
    amount_paid = Column(Integer, default=0)  # Amount paid in cents
    balance_due = Column(Integer, default=0)  # Balance due in cents
    
    # Currency and payment
    currency = Column(String(3), default="usd")
    exchange_rate = Column(Integer, default=100)  # Exchange rate * 100
    payment_terms = Column(String(50), default="net_30")
    
    # Dates
    invoice_date = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(DateTime(timezone=True))
    sent_date = Column(DateTime(timezone=True))
    viewed_date = Column(DateTime(timezone=True))
    paid_date = Column(DateTime(timezone=True))
    
    # Invoice items
    items = Column(JSON, default=list)  # Invoice line items
    notes = Column(Text)
    terms_and_conditions = Column(Text)
    
    # Payment tracking
    payment_history = Column(JSON, default=list)  # Payment history
    late_fees = Column(Integer, default=0)  # Late fees in cents
    reminder_sent_count = Column(Integer, default=0)
    last_reminder_sent = Column(DateTime(timezone=True))
    
    # Settings and metadata
    is_recurring = Column(Boolean, default=False)
    recurring_interval = Column(String(20))  # monthly, quarterly, yearly
    next_invoice_date = Column(DateTime(timezone=True))
    tags = Column(JSON, default=list)
    custom_fields = Column(JSON, default=dict)
    
    # Relationships
    organization = relationship("Organization", back_populates="project_invoices")
    project = relationship("Project", back_populates="invoices")
    customer = relationship("Customer", back_populates="invoices")
    created_by = relationship("User", foreign_keys=[created_by_id])
    
    @property
    def is_overdue(self):
        if not self.due_date or self.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.VOID]:
            return False
        from datetime import datetime
        return datetime.utcnow() > self.due_date
    
    @property
    def days_overdue(self):
        if not self.is_overdue:
            return 0
        from datetime import datetime
        return (datetime.utcnow() - self.due_date).days
    
    @property
    def payment_percentage(self):
        if self.total_amount == 0:
            return 0
        return (self.amount_paid / self.total_amount) * 100
    
    @property
    def status_color(self):
        """Get color class for status display"""
        status_colors = {
            InvoiceStatus.DRAFT: "gray",
            InvoiceStatus.SENT: "blue",
            InvoiceStatus.VIEWED: "yellow",
            InvoiceStatus.PENDING: "orange",
            InvoiceStatus.PAID: "green",
            InvoiceStatus.OVERDUE: "red",
            InvoiceStatus.PARTIALLY_PAID: "yellow",
            InvoiceStatus.CANCELLED: "gray",
            InvoiceStatus.VOID: "gray"
        }
        return status_colors.get(self.status, "gray")
    
    def calculate_totals(self):
        """Calculate invoice totals"""
        self.subtotal = sum(item.get('amount', 0) for item in self.items)
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount
        self.balance_due = self.total_amount - self.amount_paid
    
    def __repr__(self):
        return f"<ProjectInvoice(number='{self.invoice_number}', status='{self.status}')>"


class InvoiceItem(UUIDBaseModel):
    """Invoice line item model"""
    __tablename__ = "invoice_items"
    
    # Invoice relationship
    invoice_id = Column(String, ForeignKey("project_invoices.id"), nullable=False)
    
    # Item details
    description = Column(String(500), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Integer, default=0)  # Unit price in cents
    amount = Column(Integer, default=0)  # Total amount in cents
    
    # Item classification
    item_type = Column(String(50))  # service, product, expense, time
    task_id = Column(String, ForeignKey("tasks.id"))  # Related task if applicable
    
    # Tax and discount
    tax_rate = Column(Integer, default=0)  # Tax rate percentage * 100
    tax_amount = Column(Integer, default=0)  # Tax amount in cents
    discount_rate = Column(Integer, default=0)  # Discount rate percentage * 100
    discount_amount = Column(Integer, default=0)  # Discount amount in cents
    
    # Relationships
    invoice = relationship("ProjectInvoice")
    task = relationship("Task")
    
    def calculate_amount(self):
        """Calculate item total amount"""
        self.amount = self.quantity * self.unit_price
        self.tax_amount = (self.amount * self.tax_rate) // 10000  # Divide by 10000 for percentage
        self.discount_amount = (self.amount * self.discount_rate) // 10000
        self.amount = self.amount + self.tax_amount - self.discount_amount
    
    def __repr__(self):
        return f"<InvoiceItem(description='{self.description}', amount='{self.amount}')>"
