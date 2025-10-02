from .user import User
from .organization import Organization
# from .module import Module, TenantModule  # Module file doesn't exist
from .project import Project
from .task import Task
from .subscription import Subscription
from .customer import Customer
from .customer_attachment import CustomerAttachment
from .item import Item
# from .proposal import Proposal, ProposalTemplate  # Temporarily removed to fix relationship issue
from .project_invoice import ProjectInvoice, InvoiceItem
from .delivery_note import DeliveryNote, DeliveryNoteItem
from .workspace import Workspace, WorkspaceMember
from .milestone import Milestone
from .recurring_task import RecurringTaskTemplate
from .project_comment import ProjectComment
from .task_assignee import TaskAssignee
from .context_card import ContextCard
from .handoff_summary import HandoffSummary
from .decision_log import DecisionLog
from .knowledge_base import KnowledgeArticle
from .notification import Notification, NotificationPreference, NotificationRule, NotificationAnalytics
from .vendor import Vendor
from .purchase_order import PurchaseOrder, PurchaseOrderItem
from .task_document import TaskDocument

# Advanced PM Features
from .user_dashboard import (
    UserDashboardPreference, DashboardWidget, CustomField, 
    WorkflowTemplate, UserWorkflowPreference
)
from .scope_management import (
    ProjectScope, ChangeRequest, ScopeTimeline, ScopeBaseline
)
from .estimation import (
    TaskEstimate, EstimationHistory, TeamVelocity, EstimationTemplate,
    EffortComplexityMatrix, EstimationLearning
)
from .integration_hub import (
    Integration, IntegrationSyncLog, UniversalSearch, ActivityStream,
    SmartConnector, QuickAction
)
from .executive_reporting import (
    ProjectHealthIndicator, PredictiveAnalytics, ResourceAllocation,
    RiskDashboard, ExecutiveReport, KPIMetric
)
from .focus import FocusBlock
from .goal import Goal, GoalChecklist, GoalProgress, GoalReminder
from .chat import ChatRoom, ChatMessage, ChatRoomMember

__all__ = [
    "User", "Organization", "Project", "Task", "Notification", "NotificationPreference", "NotificationRule", "NotificationAnalytics", "Subscription", "Customer", "Item", 
    "ProjectInvoice", "InvoiceItem", "DeliveryNote", "DeliveryNoteItem", "Workspace", "WorkspaceMember", "Milestone", 
    "RecurringTaskTemplate", "ProjectComment", "TaskAssignee", "ContextCard",
    "HandoffSummary", "DecisionLog", "KnowledgeArticle", "Vendor", "PurchaseOrder", "PurchaseOrderItem",
    # Advanced PM Features
    "UserDashboardPreference", "DashboardWidget", "CustomField", 
    "WorkflowTemplate", "UserWorkflowPreference",
    "CustomerAttachment",
    "ProjectScope", "ChangeRequest", "ScopeTimeline", "ScopeBaseline",
    "TaskEstimate", "EstimationHistory", "TeamVelocity", "EstimationTemplate",
    "EffortComplexityMatrix", "EstimationLearning",
    "Integration", "IntegrationSyncLog", "UniversalSearch", "ActivityStream",
    "SmartConnector", "QuickAction",
    "ProjectHealthIndicator", "PredictiveAnalytics", "ResourceAllocation",
    "RiskDashboard", "ExecutiveReport", "KPIMetric",
    # Focus management
    "FocusBlock",
    # Task documents
    "TaskDocument",
    # Goals
    "Goal", "GoalChecklist", "GoalProgress", "GoalReminder",
    # Chat
    "ChatRoom", "ChatMessage", "ChatRoomMember",
]
