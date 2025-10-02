"""Intelligent Time and Estimation Schemas"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from ..models.estimation import (
    EstimationMethod, EstimationConfidence, ComplexityLevel, EffortCategory
)


class TaskEstimateBase(BaseModel):
    """Base task estimate schema"""
    estimation_method: EstimationMethod
    estimated_hours: Optional[float] = Field(None, ge=0)
    story_points: Optional[int] = Field(None, ge=0)
    confidence_level: EstimationConfidence = EstimationConfidence.MEDIUM
    confidence_percentage: Optional[float] = Field(None, ge=0, le=100)
    complexity_level: ComplexityLevel = ComplexityLevel.MODERATE
    effort_category: EffortCategory = EffortCategory.DEVELOPMENT


class TaskEstimateCreate(TaskEstimateBase):
    """Create task estimate schema"""
    task_id: str
    optimistic_hours: Optional[float] = Field(None, ge=0)
    most_likely_hours: Optional[float] = Field(None, ge=0)
    pessimistic_hours: Optional[float] = Field(None, ge=0)
    effort_breakdown: Dict[str, float] = {}
    similar_tasks: List[str] = []
    adjustment_factor: float = Field(default=1.0, ge=0.1, le=5.0)


class TaskEstimateUpdate(BaseModel):
    """Update task estimate schema"""
    estimation_method: Optional[EstimationMethod] = None
    estimated_hours: Optional[float] = Field(None, ge=0)
    story_points: Optional[int] = Field(None, ge=0)
    optimistic_hours: Optional[float] = Field(None, ge=0)
    most_likely_hours: Optional[float] = Field(None, ge=0)
    pessimistic_hours: Optional[float] = Field(None, ge=0)
    confidence_level: Optional[EstimationConfidence] = None
    confidence_percentage: Optional[float] = Field(None, ge=0, le=100)
    complexity_level: Optional[ComplexityLevel] = None
    effort_category: Optional[EffortCategory] = None
    effort_breakdown: Optional[Dict[str, float]] = None
    similar_tasks: Optional[List[str]] = None
    adjustment_factor: Optional[float] = Field(None, ge=0.1, le=5.0)
    actual_hours: Optional[float] = Field(None, ge=0)
    variance_reason: Optional[str] = None
    is_final: Optional[bool] = None
    is_revised: Optional[bool] = None


class TaskEstimate(TaskEstimateBase):
    """Task estimate schema with all fields"""
    id: str
    task_id: str
    optimistic_hours: Optional[float]
    most_likely_hours: Optional[float]
    pessimistic_hours: Optional[float]
    effort_breakdown: Dict[str, float]
    similar_tasks: List[str]
    historical_accuracy: Optional[float]
    adjustment_factor: float
    estimated_by_id: str
    estimation_date: datetime
    actual_hours: Optional[float]
    accuracy_percentage: Optional[float]
    variance_reason: Optional[str]
    ai_suggested_estimate: Optional[float]
    ai_confidence: Optional[float]
    features_used: Dict[str, Any]
    is_final: bool
    is_revised: bool
    revision_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class EstimationHistoryBase(BaseModel):
    """Base estimation history schema"""
    version: int = Field(..., ge=1)
    estimated_hours: float = Field(..., ge=0)
    actual_hours: Optional[float] = Field(None, ge=0)
    estimation_date: datetime


class EstimationHistoryCreate(EstimationHistoryBase):
    """Create estimation history schema"""
    task_id: str
    estimate_id: str
    estimator_id: str
    project_context: Dict[str, Any] = {}
    task_context: Dict[str, Any] = {}


class EstimationHistory(EstimationHistoryBase):
    """Estimation history schema with all fields"""
    id: str
    task_id: str
    estimate_id: str
    estimator_id: str
    project_context: Dict[str, Any]
    task_context: Dict[str, Any]
    accuracy_score: Optional[float]
    factors_that_helped: List[str]
    factors_that_hindered: List[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class TeamVelocityBase(BaseModel):
    """Base team velocity schema"""
    team_id: str = Field(..., min_length=1)
    period_start: datetime
    period_end: datetime
    story_points_completed: int = Field(default=0, ge=0)
    hours_logged: float = Field(default=0.0, ge=0)
    tasks_completed: int = Field(default=0, ge=0)


class TeamVelocityCreate(TeamVelocityBase):
    """Create team velocity schema"""
    team_capacity_hours: Optional[float] = Field(None, ge=0)
    utilization_percentage: Optional[float] = Field(None, ge=0, le=200)
    velocity_score: Optional[float] = Field(None, ge=0)
    bugs_introduced: int = Field(default=0, ge=0)
    rework_hours: float = Field(default=0.0, ge=0)
    quality_score: Optional[float] = Field(None, ge=0, le=100)
    team_members: List[str] = []
    team_size: Optional[int] = Field(None, ge=1)
    avg_experience_level: Optional[float] = Field(None, ge=0, le=10)
    period_type: str = Field(default="sprint", pattern="^(sprint|month|quarter)$")
    interruptions: List[Dict[str, Any]] = []
    environment_factors: Dict[str, Any] = {}


class TeamVelocityUpdate(BaseModel):
    """Update team velocity schema"""
    story_points_completed: Optional[int] = Field(None, ge=0)
    hours_logged: Optional[float] = Field(None, ge=0)
    tasks_completed: Optional[int] = Field(None, ge=0)
    team_capacity_hours: Optional[float] = Field(None, ge=0)
    utilization_percentage: Optional[float] = Field(None, ge=0, le=200)
    velocity_score: Optional[float] = Field(None, ge=0)
    bugs_introduced: Optional[int] = Field(None, ge=0)
    rework_hours: Optional[float] = Field(None, ge=0)
    quality_score: Optional[float] = Field(None, ge=0, le=100)
    team_members: Optional[List[str]] = None
    team_size: Optional[int] = Field(None, ge=1)
    avg_experience_level: Optional[float] = Field(None, ge=0, le=10)
    interruptions: Optional[List[Dict[str, Any]]] = None
    environment_factors: Optional[Dict[str, Any]] = None
    velocity_trend: Optional[str] = Field(None, pattern="^(increasing|decreasing|stable)$")
    trend_confidence: Optional[float] = Field(None, ge=0, le=100)


class TeamVelocity(TeamVelocityBase):
    """Team velocity schema with all fields"""
    id: str
    organization_id: str
    team_capacity_hours: Optional[float]
    utilization_percentage: Optional[float]
    velocity_score: Optional[float]
    bugs_introduced: int
    rework_hours: float
    quality_score: Optional[float]
    team_members: List[str]
    team_size: Optional[int]
    avg_experience_level: Optional[float]
    period_type: str
    interruptions: List[Dict[str, Any]]
    environment_factors: Dict[str, Any]
    velocity_trend: Optional[str]
    trend_confidence: Optional[float]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class EstimationTemplateBase(BaseModel):
    """Base estimation template schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    base_estimate_hours: float = Field(..., ge=0)


class EstimationTemplateCreate(EstimationTemplateBase):
    """Create estimation template schema"""
    complexity_multipliers: Dict[str, float] = {}
    effort_breakdown: Dict[str, float] = {}
    typical_factors: List[str] = []
    risk_factors: List[str] = []
    efficiency_factors: List[str] = []
    is_public: bool = False


class EstimationTemplateUpdate(BaseModel):
    """Update estimation template schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    base_estimate_hours: Optional[float] = Field(None, ge=0)
    complexity_multipliers: Optional[Dict[str, float]] = None
    effort_breakdown: Optional[Dict[str, float]] = None
    typical_factors: Optional[List[str]] = None
    risk_factors: Optional[List[str]] = None
    efficiency_factors: Optional[List[str]] = None
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None


class EstimationTemplate(EstimationTemplateBase):
    """Estimation template schema with all fields"""
    id: str
    organization_id: str
    created_by_id: str
    complexity_multipliers: Dict[str, float]
    effort_breakdown: Dict[str, float]
    typical_factors: List[str]
    risk_factors: List[str]
    efficiency_factors: List[str]
    usage_count: int
    avg_accuracy: Optional[float]
    is_public: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class EffortComplexityMatrixBase(BaseModel):
    """Base effort complexity matrix schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class EffortComplexityMatrixCreate(EffortComplexityMatrixBase):
    """Create effort complexity matrix schema"""
    effort_levels: Dict[str, Any] = {}
    complexity_levels: Dict[str, Any] = {}
    matrix_cells: Dict[str, Any] = {}
    scoring_rules: Dict[str, Any] = {}
    auto_assignment: bool = False
    is_default: bool = False


class EffortComplexityMatrixUpdate(BaseModel):
    """Update effort complexity matrix schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    effort_levels: Optional[Dict[str, Any]] = None
    complexity_levels: Optional[Dict[str, Any]] = None
    matrix_cells: Optional[Dict[str, Any]] = None
    scoring_rules: Optional[Dict[str, Any]] = None
    auto_assignment: Optional[bool] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class EffortComplexityMatrix(EffortComplexityMatrixBase):
    """Effort complexity matrix schema with all fields"""
    id: str
    organization_id: str
    created_by_id: str
    effort_levels: Dict[str, Any]
    complexity_levels: Dict[str, Any]
    matrix_cells: Dict[str, Any]
    scoring_rules: Dict[str, Any]
    auto_assignment: bool
    tasks_categorized: int
    avg_estimation_accuracy: Optional[float]
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Analysis and reporting schemas
class EstimationAccuracy(BaseModel):
    """Estimation accuracy analysis"""
    estimator_id: str
    total_estimates: int
    accurate_estimates: int
    accuracy_percentage: float
    avg_variance_percentage: float
    improvement_trend: str
    common_overestimation_factors: List[str]
    common_underestimation_factors: List[str]


class VelocityTrend(BaseModel):
    """Team velocity trend analysis"""
    team_id: str
    periods: List[Dict[str, Any]]
    avg_velocity: float
    velocity_trend: str
    trend_confidence: float
    capacity_utilization: float
    quality_trend: str
    predictions: Dict[str, Any]


class EstimationInsights(BaseModel):
    """Estimation insights and recommendations"""
    organization_id: str
    overall_accuracy: float
    top_estimators: List[Dict[str, Any]]
    accuracy_by_category: Dict[str, float]
    complexity_distribution: Dict[str, int]
    estimation_bias: Dict[str, float]
    recommendations: List[str]
    ai_model_performance: Dict[str, float]


class ConfidenceInterval(BaseModel):
    """Estimation confidence interval"""
    task_id: str
    estimated_hours: float
    confidence_level: EstimationConfidence
    lower_bound: float
    upper_bound: float
    probability_distribution: Dict[str, float]
    risk_factors: List[str]


class HistoricalPattern(BaseModel):
    """Historical estimation patterns"""
    pattern_type: str
    pattern_data: Dict[str, Any]
    accuracy_impact: float
    occurrence_frequency: float
    recommended_adjustments: List[str]
