from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime, JSON, Integer, Enum
from sqlalchemy.orm import relationship
import enum
from .base import UUIDBaseModel


class ProposalStatus(str, enum.Enum):
    """Proposal status workflow"""
    DRAFT = "DRAFT"
    SENT = "SENT"
    VIEWED = "VIEWED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    WITHDRAWN = "WITHDRAWN"


class ProposalType(str, enum.Enum):
    """Types of proposals"""
    PROJECT = "PROJECT"
    CONSULTING = "CONSULTING"
    MAINTENANCE = "MAINTENANCE"
    SUPPORT = "SUPPORT"
    CUSTOM = "CUSTOM"


class Proposal(UUIDBaseModel):
    """Proposal model for business proposals"""
    __tablename__ = "proposals"
    
    # Basic proposal info
    title = Column(String(255), nullable=False)
    description = Column(Text)
    proposal_number = Column(String(100), unique=True, nullable=False, index=True)
    
    # Organization and customer relationships
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)  # Optional link to project
    
    # Proposal details
    proposal_type = Column(Enum(ProposalType), default=ProposalType.PROJECT)
    status = Column(Enum(ProposalStatus), default=ProposalStatus.DRAFT)
    
    # Content and structure
    content = Column(JSON, default=dict)  # Structured proposal content
    template_id = Column(String(100))  # Reference to proposal template
    custom_template = Column(JSON, default=dict)  # Custom template data
    
    # Financial information
    total_amount = Column(Integer)  # Total amount in cents
    currency = Column(String(3), default="usd")
    valid_until = Column(DateTime(timezone=True))  # Proposal expiration
    
    # Dates and tracking
    sent_date = Column(DateTime(timezone=True))
    viewed_date = Column(DateTime(timezone=True))
    responded_date = Column(DateTime(timezone=True))
    
    # Response tracking
    response_notes = Column(Text)
    rejection_reason = Column(Text)
    follow_up_date = Column(DateTime(timezone=True))
    
    # Settings and metadata
    is_template = Column(Boolean, default=False)
    notes = Column(Text)  # General notes about the proposal
    tags = Column(JSON, default=list)
    custom_fields = Column(JSON, default=dict)
    
    # Relationships
    organization = relationship("Organization")
    customer = relationship("app.models.customer.Customer")
    created_by = relationship("User", foreign_keys=[created_by_id])
    # Note: project relationship removed to fix startup issue - can be added back later with proper migration
    
    @property
    def is_expired(self):
        if not self.valid_until:
            return False
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return now > self.valid_until and self.status == ProposalStatus.SENT
    
    @property
    def status_color(self):
        """Get color class for status display"""
        status_colors = {
            ProposalStatus.DRAFT: "gray",
            ProposalStatus.SENT: "blue",
            ProposalStatus.VIEWED: "yellow",
            ProposalStatus.ACCEPTED: "green",
            ProposalStatus.REJECTED: "red",
            ProposalStatus.EXPIRED: "orange",
            ProposalStatus.WITHDRAWN: "gray"
        }
        return status_colors.get(self.status, "gray")
    
    def __repr__(self):
        return f"<Proposal(title='{self.title}', status='{self.status}')>"


class ProposalTemplate(UUIDBaseModel):
    """Proposal template model"""
    __tablename__ = "proposal_templates"
    
    # Template info
    name = Column(String(255), nullable=False)
    description = Column(Text)
    is_default = Column(Boolean, default=False)
    
    # Organization relationship
    # Using UUID type for consistency with organization.id
    organization_id = Column(String, nullable=False)
    
    # Template structure
    sections = Column(JSON, default=list)  # Template sections structure
    styling = Column(JSON, default=dict)  # Template styling options
    variables = Column(JSON, default=list)  # Available template variables
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime(timezone=True))
    
    # Relationships
    # Using foreign_keys parameter to specify the relationship without a foreign key constraint
    organization = relationship("Organization", foreign_keys=[organization_id], primaryjoin="ProposalTemplate.organization_id == Organization.id")
    
    def __repr__(self):
        return f"<ProposalTemplate(name='{self.name}')>"
