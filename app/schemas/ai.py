from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class RiskRequest(BaseModel):
    project_id: str
    task_id: Optional[str] = None
    context: Dict[str, Any] = {}

class RiskResponse(BaseModel):
    risk_id: str
    score: float
    severity: str
    explanation: str
    factors: Dict[str, Any]

class ResourceOptimizationRequest(BaseModel):
    project_id: str
    candidates: List[Dict[str, Any]]  # [{user_id, skills:[], availability, workload}]
    tasks: List[Dict[str, Any]]      # [{task_id, skills_required:[], effort_estimate}]

class ResourceOptimizationResult(BaseModel):
    assignments: List[Dict[str, Any]]  # [{task_id, user_id, rationale}]
    conflicts: List[Dict[str, Any]]

class WorkflowAutomationRequest(BaseModel):
    project_id: str
    instruction: str  # natural language instruction

class WorkflowAutomationResult(BaseModel):
    actions: List[Dict[str, Any]]  # structured actions: create_task, reminder, approval, etc

class NLCommand(BaseModel):
    prompt: str
    project_id: Optional[str] = None

class NLResult(BaseModel):
    actions: List[Dict[str, Any]]
    summary: Optional[str] = None

class MeetingSummaryRequest(BaseModel):
    project_id: Optional[str]
    transcript: str

class MeetingSummaryResult(BaseModel):
    summary: str
    action_items: List[Dict[str, Any]]
    decisions: List[str]
    sentiments: Dict[str, Any]

class ScenarioRequest(BaseModel):
    project_id: str
    assumptions: Dict[str, Any]

class ScenarioResult(BaseModel):
    impact: Dict[str, Any]
    recommendation: str

class ForecastRequest(BaseModel):
    project_id: str
    forecast_type: str = Field(default="timeline")  # timeline or budget
    inputs: Dict[str, Any] = {}

class ForecastResult(BaseModel):
    outputs: Dict[str, Any]
    confidence: float

