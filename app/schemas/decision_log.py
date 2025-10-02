from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from ..models.decision_log import DecisionStatus, DecisionImpact, DecisionCategory


class DecisionLogBase(BaseModel):
    title: str
    description: str
    category: DecisionCategory
    impact_level: Optional[DecisionImpact] = DecisionImpact.MEDIUM
    problem_statement: str
    rationale: str
    alternatives_considered: Optional[List[str]] = []
    assumptions: Optional[List[str]] = []
    constraints: Optional[List[str]] = []
    decision_outcome: Optional[str] = None
    success_criteria: Optional[List[str]] = []
    risks: Optional[List[str]] = []
    mitigation_strategies: Optional[List[str]] = []
    stakeholders: Optional[List[str]] = []
    approvers: Optional[List[str]] = []
    related_tasks: Optional[List[str]] = []
    related_decisions: Optional[List[str]] = []
    supporting_documents: Optional[List[str]] = []
    evidence: Optional[List[str]] = []
    communication_plan: Optional[List[str]] = []
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    review_date: Optional[datetime] = None


class DecisionLogCreate(DecisionLogBase):
    project_id: str


class DecisionLogUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[DecisionStatus] = None
    category: Optional[DecisionCategory] = None
    impact_level: Optional[DecisionImpact] = None
    problem_statement: Optional[str] = None
    rationale: Optional[str] = None
    alternatives_considered: Optional[List[str]] = None
    assumptions: Optional[List[str]] = None
    constraints: Optional[List[str]] = None
    decision_outcome: Optional[str] = None
    success_criteria: Optional[List[str]] = None
    risks: Optional[List[str]] = None
    mitigation_strategies: Optional[List[str]] = None
    stakeholders: Optional[List[str]] = None
    approvers: Optional[List[str]] = None
    related_tasks: Optional[List[str]] = None
    related_decisions: Optional[List[str]] = None
    implementation_date: Optional[datetime] = None
    implementation_notes: Optional[str] = None
    supporting_documents: Optional[List[str]] = None
    evidence: Optional[List[str]] = None
    communication_plan: Optional[List[str]] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    review_date: Optional[datetime] = None
    follow_up_actions: Optional[List[str]] = None
    lessons_learned: Optional[str] = None


class DecisionLog(DecisionLogBase):
    id: str
    project_id: str
    decision_number: int
    status: DecisionStatus
    decision_maker_id: str
    decision_date: datetime
    implementation_date: Optional[datetime]
    implementation_notes: Optional[str]
    follow_up_actions: Optional[List[str]]
    lessons_learned: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DecisionLogResponse(DecisionLog):
    """Response model with additional computed fields"""
    decision_maker_name: Optional[str] = None
    project_name: Optional[str] = None
    stakeholder_names: Optional[List[str]] = []
    approver_names: Optional[List[str]] = []
    
    class Config:
        from_attributes = True





