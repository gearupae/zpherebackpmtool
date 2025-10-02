"""Executive-Ready Reporting Schemas"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from ..models.executive_reporting import (
    HealthStatus, RiskLevel, PredictionConfidence, ReportFrequency
)


class ProjectHealthIndicatorBase(BaseModel):
    """Base project health indicator schema"""
    overall_health: HealthStatus = HealthStatus.GREEN
    health_score: Optional[float] = Field(None, ge=0, le=100)
    schedule_health: HealthStatus = HealthStatus.GREEN
    budget_health: HealthStatus = HealthStatus.GREEN
    scope_health: HealthStatus = HealthStatus.GREEN
    quality_health: HealthStatus = HealthStatus.GREEN
    team_health: HealthStatus = HealthStatus.GREEN


class ProjectHealthIndicatorCreate(ProjectHealthIndicatorBase):
    """Create project health indicator schema"""
    project_id: str
    schedule_variance_percentage: Optional[float] = None
    budget_variance_percentage: Optional[float] = None
    scope_completion_percentage: Optional[float] = Field(None, ge=0, le=100)
    quality_score: Optional[float] = Field(None, ge=0, le=100)
    team_velocity_score: Optional[float] = Field(None, ge=0)
    identified_risks_count: int = Field(default=0, ge=0)
    high_priority_risks_count: int = Field(default=0, ge=0)
    overdue_tasks_count: int = Field(default=0, ge=0)
    blocked_tasks_count: int = Field(default=0, ge=0)
    health_summary: Optional[str] = None
    improvement_recommendations: List[str] = []
    escalation_required: bool = False


class ProjectHealthIndicatorUpdate(BaseModel):
    """Update project health indicator schema"""
    overall_health: Optional[HealthStatus] = None
    health_score: Optional[float] = Field(None, ge=0, le=100)
    schedule_health: Optional[HealthStatus] = None
    budget_health: Optional[HealthStatus] = None
    scope_health: Optional[HealthStatus] = None
    quality_health: Optional[HealthStatus] = None
    team_health: Optional[HealthStatus] = None
    schedule_variance_percentage: Optional[float] = None
    budget_variance_percentage: Optional[float] = None
    scope_completion_percentage: Optional[float] = Field(None, ge=0, le=100)
    quality_score: Optional[float] = Field(None, ge=0, le=100)
    team_velocity_score: Optional[float] = Field(None, ge=0)
    identified_risks_count: Optional[int] = Field(None, ge=0)
    high_priority_risks_count: Optional[int] = Field(None, ge=0)
    overdue_tasks_count: Optional[int] = Field(None, ge=0)
    blocked_tasks_count: Optional[int] = Field(None, ge=0)
    health_summary: Optional[str] = None
    improvement_recommendations: Optional[List[str]] = None
    escalation_required: Optional[bool] = None
    health_trend: Optional[str] = Field(None, pattern="^(improving|declining|stable)$")
    trend_confidence: Optional[float] = Field(None, ge=0, le=100)
    next_assessment_date: Optional[datetime] = None


class ProjectHealthIndicator(ProjectHealthIndicatorBase):
    """Project health indicator schema with all fields"""
    id: str
    project_id: str
    schedule_variance_percentage: Optional[float]
    budget_variance_percentage: Optional[float]
    scope_completion_percentage: Optional[float]
    quality_score: Optional[float]
    team_velocity_score: Optional[float]
    identified_risks_count: int
    high_priority_risks_count: int
    overdue_tasks_count: int
    blocked_tasks_count: int
    health_trend: Optional[str]
    trend_confidence: Optional[float]
    assessment_date: datetime
    assessed_by_id: Optional[str]
    next_assessment_date: Optional[datetime]
    health_summary: Optional[str]
    improvement_recommendations: List[str]
    escalation_required: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PredictiveAnalyticsBase(BaseModel):
    """Base predictive analytics schema"""
    entity_type: str = Field(..., max_length=50)
    entity_id: str
    prediction_type: str = Field(..., max_length=100)
    confidence_level: PredictionConfidence = PredictionConfidence.MEDIUM
    confidence_percentage: Optional[float] = Field(None, ge=0, le=100)


class PredictiveAnalyticsCreate(PredictiveAnalyticsBase):
    """Create predictive analytics schema"""
    model_config = ConfigDict(protected_namespaces=())
    predicted_value: Dict[str, Any] = {}
    model_name: Optional[str] = Field(None, max_length=255)
    model_version: Optional[str] = Field(None, max_length=50)
    features_used: List[str] = []
    prediction_horizon_days: Optional[int] = Field(None, ge=1)
    baseline_scenario: Dict[str, Any] = {}
    best_case_scenario: Dict[str, Any] = {}
    worst_case_scenario: Dict[str, Any] = {}
    most_likely_scenario: Dict[str, Any] = {}
    key_factors: List[str] = []
    assumptions: List[str] = []
    risk_factors: List[str] = []


class PredictiveAnalyticsUpdate(BaseModel):
    """Update predictive analytics schema"""
    model_config = ConfigDict(protected_namespaces=())
    predicted_value: Optional[Dict[str, Any]] = None
    confidence_level: Optional[PredictionConfidence] = None
    confidence_percentage: Optional[float] = Field(None, ge=0, le=100)
    model_name: Optional[str] = Field(None, max_length=255)
    model_version: Optional[str] = Field(None, max_length=50)
    features_used: Optional[List[str]] = None
    prediction_horizon_days: Optional[int] = Field(None, ge=1)
    baseline_scenario: Optional[Dict[str, Any]] = None
    best_case_scenario: Optional[Dict[str, Any]] = None
    worst_case_scenario: Optional[Dict[str, Any]] = None
    most_likely_scenario: Optional[Dict[str, Any]] = None
    key_factors: Optional[List[str]] = None
    assumptions: Optional[List[str]] = None
    risk_factors: Optional[List[str]] = None
    actual_outcome: Optional[Dict[str, Any]] = None
    prediction_accuracy: Optional[float] = Field(None, ge=0, le=100)
    variance_analysis: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    needs_update: Optional[bool] = None


class PredictiveAnalytics(PredictiveAnalyticsBase):
    """Predictive analytics schema with all fields"""
    id: str
    organization_id: str
    predicted_value: Dict[str, Any]
    model_name: Optional[str]
    model_version: Optional[str]
    features_used: List[str]
    prediction_date: datetime
    prediction_horizon_days: Optional[int]
    baseline_scenario: Dict[str, Any]
    best_case_scenario: Dict[str, Any]
    worst_case_scenario: Dict[str, Any]
    most_likely_scenario: Dict[str, Any]
    key_factors: List[str]
    assumptions: List[str]
    risk_factors: List[str]
    actual_outcome: Optional[Dict[str, Any]]
    prediction_accuracy: Optional[float]
    variance_analysis: Dict[str, Any]
    is_active: bool
    needs_update: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ResourceAllocationBase(BaseModel):
    """Base resource allocation schema"""
    period_start: datetime
    period_end: datetime
    total_capacity_hours: Optional[float] = Field(None, ge=0)
    allocated_hours: Optional[float] = Field(None, ge=0)
    utilization_percentage: Optional[float] = Field(None, ge=0, le=200)


class ResourceAllocationCreate(ResourceAllocationBase):
    """Create resource allocation schema"""
    total_team_members: Optional[int] = Field(None, ge=0)
    available_members: Optional[int] = Field(None, ge=0)
    on_leave_members: int = Field(default=0, ge=0)
    overallocated_members: int = Field(default=0, ge=0)
    skill_gaps: List[str] = []
    skill_surpluses: List[str] = []
    critical_skills_coverage: Optional[float] = Field(None, ge=0, le=100)
    identified_bottlenecks: List[Dict[str, Any]] = []
    bottleneck_impact: Dict[str, Any] = {}
    mitigation_strategies: List[str] = []
    project_allocations: Dict[str, Any] = {}
    priority_conflicts: List[Dict[str, Any]] = []
    future_demand: Dict[str, Any] = {}
    hiring_recommendations: List[str] = []
    reallocation_opportunities: List[Dict[str, Any]] = []


class ResourceAllocationUpdate(BaseModel):
    """Update resource allocation schema"""
    total_capacity_hours: Optional[float] = Field(None, ge=0)
    allocated_hours: Optional[float] = Field(None, ge=0)
    utilization_percentage: Optional[float] = Field(None, ge=0, le=200)
    total_team_members: Optional[int] = Field(None, ge=0)
    available_members: Optional[int] = Field(None, ge=0)
    on_leave_members: Optional[int] = Field(None, ge=0)
    overallocated_members: Optional[int] = Field(None, ge=0)
    skill_gaps: Optional[List[str]] = None
    skill_surpluses: Optional[List[str]] = None
    critical_skills_coverage: Optional[float] = Field(None, ge=0, le=100)
    identified_bottlenecks: Optional[List[Dict[str, Any]]] = None
    bottleneck_impact: Optional[Dict[str, Any]] = None
    mitigation_strategies: Optional[List[str]] = None
    project_allocations: Optional[Dict[str, Any]] = None
    priority_conflicts: Optional[List[Dict[str, Any]]] = None
    future_demand: Optional[Dict[str, Any]] = None
    hiring_recommendations: Optional[List[str]] = None
    reallocation_opportunities: Optional[List[Dict[str, Any]]] = None


class ResourceAllocation(ResourceAllocationBase):
    """Resource allocation schema with all fields"""
    id: str
    organization_id: str
    total_team_members: Optional[int]
    available_members: Optional[int]
    on_leave_members: int
    overallocated_members: int
    skill_gaps: List[str]
    skill_surpluses: List[str]
    critical_skills_coverage: Optional[float]
    identified_bottlenecks: List[Dict[str, Any]]
    bottleneck_impact: Dict[str, Any]
    mitigation_strategies: List[str]
    project_allocations: Dict[str, Any]
    priority_conflicts: List[Dict[str, Any]]
    future_demand: Dict[str, Any]
    hiring_recommendations: List[str]
    reallocation_opportunities: List[Dict[str, Any]]
    analysis_date: datetime
    analyzed_by_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class RiskDashboardBase(BaseModel):
    """Base risk dashboard schema"""
    risk_name: str = Field(..., min_length=1, max_length=255)
    risk_description: str = Field(..., min_length=1)
    risk_category: Optional[str] = Field(None, max_length=100)
    entity_type: str = Field(..., max_length=50)
    entity_id: str
    risk_level: RiskLevel = RiskLevel.MEDIUM
    probability_percentage: Optional[float] = Field(None, ge=0, le=100)
    impact_score: Optional[float] = Field(None, ge=0, le=100)
    risk_score: Optional[float] = Field(None, ge=0, le=100)


class RiskDashboardCreate(RiskDashboardBase):
    """Create risk dashboard schema"""
    triggers: List[str] = []
    indicators: List[str] = []
    consequences: List[str] = []
    mitigation_strategies: List[str] = []
    contingency_plans: List[str] = []
    response_plan: Optional[str] = None
    risk_owner_id: Optional[str] = None
    responsible_team: List[str] = []
    monitoring_frequency: str = Field(default="weekly", pattern="^(daily|weekly|monthly)$")


class RiskDashboardUpdate(BaseModel):
    """Update risk dashboard schema"""
    risk_name: Optional[str] = Field(None, min_length=1, max_length=255)
    risk_description: Optional[str] = None
    risk_category: Optional[str] = Field(None, max_length=100)
    risk_level: Optional[RiskLevel] = None
    probability_percentage: Optional[float] = Field(None, ge=0, le=100)
    impact_score: Optional[float] = Field(None, ge=0, le=100)
    risk_score: Optional[float] = Field(None, ge=0, le=100)
    triggers: Optional[List[str]] = None
    indicators: Optional[List[str]] = None
    consequences: Optional[List[str]] = None
    mitigation_strategies: Optional[List[str]] = None
    contingency_plans: Optional[List[str]] = None
    response_plan: Optional[str] = None
    risk_owner_id: Optional[str] = None
    responsible_team: Optional[List[str]] = None
    monitoring_frequency: Optional[str] = Field(None, pattern="^(daily|weekly|monthly)$")
    last_reviewed_date: Optional[datetime] = None
    next_review_date: Optional[datetime] = None
    risk_status: Optional[str] = Field(None, pattern="^(active|mitigated|occurred|closed)$")
    escalation_level: Optional[int] = Field(None, ge=0, le=2)
    requires_attention: Optional[bool] = None
    risk_history: Optional[List[Dict[str, Any]]] = None
    mitigation_effectiveness: Optional[float] = Field(None, ge=0, le=100)


class RiskDashboard(RiskDashboardBase):
    """Risk dashboard schema with all fields"""
    id: str
    organization_id: str
    triggers: List[str]
    indicators: List[str]
    consequences: List[str]
    mitigation_strategies: List[str]
    contingency_plans: List[str]
    response_plan: Optional[str]
    risk_owner_id: Optional[str]
    responsible_team: List[str]
    monitoring_frequency: str
    last_reviewed_date: Optional[datetime]
    next_review_date: Optional[datetime]
    risk_status: str
    escalation_level: int
    requires_attention: bool
    risk_history: List[Dict[str, Any]]
    mitigation_effectiveness: Optional[float]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ExecutiveReportBase(BaseModel):
    """Base executive report schema"""
    report_name: str = Field(..., min_length=1, max_length=255)
    report_type: str = Field(..., max_length=100)
    report_category: Optional[str] = Field(None, max_length=100)
    executive_summary: Optional[str] = None
    report_frequency: ReportFrequency = ReportFrequency.WEEKLY


class ExecutiveReportCreate(ExecutiveReportBase):
    """Create executive report schema"""
    key_metrics: Dict[str, Any] = {}
    health_indicators: Dict[str, Any] = {}
    trend_analysis: Dict[str, Any] = {}
    risk_analysis: Dict[str, Any] = {}
    opportunity_analysis: Dict[str, Any] = {}
    recommendations: List[str] = []
    action_items: List[Dict[str, Any]] = []
    decisions_required: List[Dict[str, Any]] = []
    data_period_start: Optional[datetime] = None
    data_period_end: Optional[datetime] = None
    target_audience: List[str] = []
    distribution_list: List[str] = []
    access_permissions: List[str] = []
    is_automated: bool = False


class ExecutiveReportUpdate(BaseModel):
    """Update executive report schema"""
    report_name: Optional[str] = Field(None, min_length=1, max_length=255)
    report_type: Optional[str] = Field(None, max_length=100)
    report_category: Optional[str] = Field(None, max_length=100)
    executive_summary: Optional[str] = None
    key_metrics: Optional[Dict[str, Any]] = None
    health_indicators: Optional[Dict[str, Any]] = None
    trend_analysis: Optional[Dict[str, Any]] = None
    risk_analysis: Optional[Dict[str, Any]] = None
    opportunity_analysis: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[str]] = None
    action_items: Optional[List[Dict[str, Any]]] = None
    decisions_required: Optional[List[Dict[str, Any]]] = None
    data_period_start: Optional[datetime] = None
    data_period_end: Optional[datetime] = None
    report_frequency: Optional[ReportFrequency] = None
    target_audience: Optional[List[str]] = None
    distribution_list: Optional[List[str]] = None
    access_permissions: Optional[List[str]] = None
    is_published: Optional[bool] = None
    is_automated: Optional[bool] = None
    next_generation_date: Optional[datetime] = None


class ExecutiveReport(ExecutiveReportBase):
    """Executive report schema with all fields"""
    id: str
    organization_id: str
    created_by_id: str
    key_metrics: Dict[str, Any]
    health_indicators: Dict[str, Any]
    trend_analysis: Dict[str, Any]
    risk_analysis: Dict[str, Any]
    opportunity_analysis: Dict[str, Any]
    recommendations: List[str]
    action_items: List[Dict[str, Any]]
    decisions_required: List[Dict[str, Any]]
    data_period_start: Optional[datetime]
    data_period_end: Optional[datetime]
    target_audience: List[str]
    distribution_list: List[str]
    access_permissions: List[str]
    is_published: bool
    is_automated: bool
    generation_time_seconds: Optional[float]
    report_date: datetime
    next_generation_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class KPIMetricBase(BaseModel):
    """Base KPI metric schema"""
    metric_name: str = Field(..., min_length=1, max_length=255)
    metric_description: Optional[str] = None
    metric_category: Optional[str] = Field(None, max_length=100)
    measurement_unit: Optional[str] = Field(None, max_length=50)
    target_value: Optional[float] = None
    current_value: Optional[float] = None


class KPIMetricCreate(KPIMetricBase):
    """Create KPI metric schema"""
    threshold_green: Optional[float] = None
    threshold_yellow: Optional[float] = None
    threshold_red: Optional[float] = None
    calculation_method: Optional[str] = Field(None, max_length=100)
    calculation_formula: Optional[str] = None
    data_sources: List[str] = []
    is_executive_metric: bool = False
    reporting_frequency: ReportFrequency = ReportFrequency.WEEKLY
    alert_on_threshold: bool = True
    metric_owner_id: Optional[str] = None
    stakeholders: List[str] = []


class KPIMetricUpdate(BaseModel):
    """Update KPI metric schema"""
    metric_name: Optional[str] = Field(None, min_length=1, max_length=255)
    metric_description: Optional[str] = None
    metric_category: Optional[str] = Field(None, max_length=100)
    measurement_unit: Optional[str] = Field(None, max_length=50)
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    threshold_green: Optional[float] = None
    threshold_yellow: Optional[float] = None
    threshold_red: Optional[float] = None
    current_status: Optional[HealthStatus] = None
    calculation_method: Optional[str] = Field(None, max_length=100)
    calculation_formula: Optional[str] = None
    data_sources: Optional[List[str]] = None
    historical_values: Optional[List[Dict[str, Any]]] = None
    trend_direction: Optional[str] = Field(None, pattern="^(improving|declining|stable)$")
    trend_confidence: Optional[float] = Field(None, ge=0, le=100)
    is_executive_metric: Optional[bool] = None
    reporting_frequency: Optional[ReportFrequency] = None
    alert_on_threshold: Optional[bool] = None
    metric_owner_id: Optional[str] = None
    stakeholders: Optional[List[str]] = None
    is_active: Optional[bool] = None


class KPIMetric(KPIMetricBase):
    """KPI metric schema with all fields"""
    id: str
    organization_id: str
    created_by_id: str
    threshold_green: Optional[float]
    threshold_yellow: Optional[float]
    threshold_red: Optional[float]
    current_status: HealthStatus
    last_updated: datetime
    calculation_method: Optional[str]
    calculation_formula: Optional[str]
    data_sources: List[str]
    historical_values: List[Dict[str, Any]]
    trend_direction: Optional[str]
    trend_confidence: Optional[float]
    is_executive_metric: bool
    reporting_frequency: ReportFrequency
    alert_on_threshold: bool
    metric_owner_id: Optional[str]
    stakeholders: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Dashboard and summary schemas
class ExecutiveDashboard(BaseModel):
    """Executive dashboard summary"""
    organization_id: str
    overall_health: HealthStatus
    total_projects: int
    active_projects: int
    at_risk_projects: int
    completed_projects: int
    total_budget: float
    budget_utilization: float
    team_utilization: float
    key_metrics: List[Dict[str, Any]]
    health_indicators: List[Dict[str, Any]]
    top_risks: List[Dict[str, Any]]
    upcoming_deadlines: List[Dict[str, Any]]
    generated_at: datetime


class HealthIndicatorSummary(BaseModel):
    """Health indicator summary"""
    indicator_name: str
    current_status: HealthStatus
    current_value: Optional[float]
    target_value: Optional[float]
    trend: str
    last_updated: datetime
    requires_attention: bool


class PredictionSummary(BaseModel):
    """Prediction summary"""
    entity_id: str
    entity_type: str
    prediction_type: str
    predicted_outcome: str
    confidence: PredictionConfidence
    key_factors: List[str]
    predicted_date: Optional[datetime]
    created_at: datetime


class RiskSummary(BaseModel):
    """Risk summary"""
    risk_id: str
    risk_name: str
    risk_level: RiskLevel
    probability: float
    impact: float
    risk_score: float
    status: str
    owner: Optional[str]
    next_review: Optional[datetime]
