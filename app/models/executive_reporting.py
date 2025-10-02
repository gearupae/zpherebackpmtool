"""Executive-Ready Reporting Models"""
import enum
from sqlalchemy import Column, String, Text, JSON, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import UUIDBaseModel


class HealthStatus(str, enum.Enum):
    """Health indicator statuses"""
    GREEN = "green"      # On track, no issues
    YELLOW = "yellow"    # Some concerns, monitor closely
    RED = "red"          # Critical issues, needs attention


class RiskLevel(str, enum.Enum):
    """Risk levels for projects and initiatives"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PredictionConfidence(str, enum.Enum):
    """Confidence levels for predictive analytics"""
    VERY_LOW = "very_low"      # 0-20%
    LOW = "low"                # 20-40%
    MEDIUM = "medium"          # 40-60%
    HIGH = "high"              # 60-80%
    VERY_HIGH = "very_high"    # 80-100%


class ReportFrequency(str, enum.Enum):
    """Report generation frequency"""
    REAL_TIME = "real_time"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class ProjectHealthIndicator(UUIDBaseModel):
    """Project health indicators and status tracking"""
    __tablename__ = "project_health_indicators"
    
    # Project relationship
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    # Overall health
    overall_health = Column(SQLEnum(HealthStatus), default=HealthStatus.GREEN)
    health_score = Column(Float)  # Numeric health score (0-100)
    
    # Individual health metrics
    schedule_health = Column(SQLEnum(HealthStatus), default=HealthStatus.GREEN)
    budget_health = Column(SQLEnum(HealthStatus), default=HealthStatus.GREEN)
    scope_health = Column(SQLEnum(HealthStatus), default=HealthStatus.GREEN)
    quality_health = Column(SQLEnum(HealthStatus), default=HealthStatus.GREEN)
    team_health = Column(SQLEnum(HealthStatus), default=HealthStatus.GREEN)
    
    # Detailed metrics
    schedule_variance_percentage = Column(Float)  # Positive = ahead, negative = behind
    budget_variance_percentage = Column(Float)   # Budget variance
    scope_completion_percentage = Column(Float)   # Scope completion
    quality_score = Column(Float)                 # Quality metrics (0-100)
    team_velocity_score = Column(Float)           # Team performance score
    
    # Risk indicators
    identified_risks_count = Column(Integer, default=0)
    high_priority_risks_count = Column(Integer, default=0)
    overdue_tasks_count = Column(Integer, default=0)
    blocked_tasks_count = Column(Integer, default=0)
    
    # Trends
    health_trend = Column(String(20))  # improving, declining, stable
    trend_confidence = Column(Float)   # Confidence in trend assessment
    
    # Assessment metadata
    assessment_date = Column(DateTime(timezone=True), server_default=func.now())
    assessed_by_id = Column(String, ForeignKey("users.id"))
    next_assessment_date = Column(DateTime(timezone=True))
    
    # Comments and notes
    health_summary = Column(Text)
    improvement_recommendations = Column(JSON, default=list)
    escalation_required = Column(Boolean, default=False)
    
    # Relationships
    project = relationship("Project")
    assessed_by = relationship("User")
    
    def __repr__(self):
        return f"<ProjectHealthIndicator(project_id='{self.project_id}', health='{self.overall_health}')>"


class PredictiveAnalytics(UUIDBaseModel):
    """Predictive analytics for project outcomes"""
    __tablename__ = "predictive_analytics"
    
    # Target entity
    entity_type = Column(String(50), nullable=False)  # project, task, milestone
    entity_id = Column(String, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Prediction details
    prediction_type = Column(String(100), nullable=False)  # completion_date, budget_overrun, etc.
    predicted_value = Column(JSON, nullable=False)  # The actual prediction
    confidence_level = Column(SQLEnum(PredictionConfidence), default=PredictionConfidence.MEDIUM)
    confidence_percentage = Column(Float)  # Numeric confidence (0-100)
    
    # Model information
    model_name = Column(String(255))
    model_version = Column(String(50))
    features_used = Column(JSON, default=list)  # Features used for prediction
    
    # Prediction context
    prediction_date = Column(DateTime(timezone=True), server_default=func.now())
    prediction_horizon_days = Column(Integer)  # How far into future
    baseline_scenario = Column(JSON, default=dict)  # Current state data
    
    # Scenario analysis
    best_case_scenario = Column(JSON, default=dict)
    worst_case_scenario = Column(JSON, default=dict)
    most_likely_scenario = Column(JSON, default=dict)
    
    # Factors and assumptions
    key_factors = Column(JSON, default=list)  # Key factors affecting prediction
    assumptions = Column(JSON, default=list)  # Underlying assumptions
    risk_factors = Column(JSON, default=list)  # Factors that could affect outcome
    
    # Validation and accuracy
    actual_outcome = Column(JSON)  # Actual outcome when available
    prediction_accuracy = Column(Float)  # How accurate was this prediction
    variance_analysis = Column(JSON, default=dict)  # Analysis of variance
    
    # Status
    is_active = Column(Boolean, default=True)
    needs_update = Column(Boolean, default=False)
    
    # Relationships
    organization = relationship("Organization")
    
    def __repr__(self):
        return f"<PredictiveAnalytics(type='{self.prediction_type}', entity='{self.entity_id}')>"


class ResourceAllocation(UUIDBaseModel):
    """Resource allocation and capacity analysis"""
    __tablename__ = "resource_allocation"
    
    # Time period
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Resource metrics
    total_capacity_hours = Column(Float)  # Total available hours
    allocated_hours = Column(Float)       # Hours allocated to projects
    utilization_percentage = Column(Float)  # Allocation percentage
    
    # Team composition
    total_team_members = Column(Integer)
    available_members = Column(Integer)
    on_leave_members = Column(Integer)
    overallocated_members = Column(Integer)
    
    # Skill analysis
    skill_gaps = Column(JSON, default=list)  # Identified skill gaps
    skill_surpluses = Column(JSON, default=list)  # Surplus skills
    critical_skills_coverage = Column(Float)  # Coverage of critical skills
    
    # Bottleneck analysis
    identified_bottlenecks = Column(JSON, default=list)  # Resource bottlenecks
    bottleneck_impact = Column(JSON, default=dict)  # Impact of bottlenecks
    mitigation_strategies = Column(JSON, default=list)  # Strategies to address bottlenecks
    
    # Allocation by project
    project_allocations = Column(JSON, default=dict)  # Allocation breakdown by project
    priority_conflicts = Column(JSON, default=list)  # Conflicts in priorities
    
    # Forecast
    future_demand = Column(JSON, default=dict)  # Forecasted resource demand
    hiring_recommendations = Column(JSON, default=list)  # Recommended hires
    reallocation_opportunities = Column(JSON, default=list)  # Reallocation opportunities
    
    # Analysis metadata
    analysis_date = Column(DateTime(timezone=True), server_default=func.now())
    analyzed_by_id = Column(String, ForeignKey("users.id"))
    
    # Relationships
    organization = relationship("Organization")
    analyzed_by = relationship("User")
    
    def __repr__(self):
        return f"<ResourceAllocation(org='{self.organization_id}', utilization={self.utilization_percentage}%)>"


class RiskDashboard(UUIDBaseModel):
    """Risk identification and monitoring dashboard"""
    __tablename__ = "risk_dashboard"
    
    # Risk metadata
    risk_name = Column(String(255), nullable=False)
    risk_description = Column(Text, nullable=False)
    risk_category = Column(String(100))  # technical, schedule, budget, resource, external
    
    # Entity relationship
    entity_type = Column(String(50), nullable=False)  # project, organization, task
    entity_id = Column(String, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Risk assessment
    risk_level = Column(SQLEnum(RiskLevel), default=RiskLevel.MEDIUM)
    probability_percentage = Column(Float)  # Probability of occurrence (0-100)
    impact_score = Column(Float)           # Impact if occurs (0-100)
    risk_score = Column(Float)             # Overall risk score (probability * impact)
    
    # Risk details
    triggers = Column(JSON, default=list)      # What could trigger this risk
    indicators = Column(JSON, default=list)    # Early warning indicators
    consequences = Column(JSON, default=list)  # Potential consequences
    
    # Mitigation and response
    mitigation_strategies = Column(JSON, default=list)  # Risk mitigation strategies
    contingency_plans = Column(JSON, default=list)      # Contingency plans
    response_plan = Column(Text)                         # Risk response plan
    
    # Ownership and responsibility
    risk_owner_id = Column(String, ForeignKey("users.id"))  # Risk owner
    responsible_team = Column(JSON, default=list)           # Responsible team members
    
    # Monitoring
    monitoring_frequency = Column(String(20), default="weekly")  # Monitoring frequency
    last_reviewed_date = Column(DateTime(timezone=True))
    next_review_date = Column(DateTime(timezone=True))
    
    # Status tracking
    risk_status = Column(String(20), default="active")  # active, mitigated, occurred, closed
    escalation_level = Column(Integer, default=0)       # 0=normal, 1=elevated, 2=critical
    requires_attention = Column(Boolean, default=False)
    
    # Historical tracking
    risk_history = Column(JSON, default=list)  # History of risk changes
    mitigation_effectiveness = Column(Float)    # Effectiveness of mitigation (0-100)
    
    # Relationships
    organization = relationship("Organization")
    risk_owner = relationship("User")
    
    def __repr__(self):
        return f"<RiskDashboard(name='{self.risk_name}', level='{self.risk_level}')>"


class ExecutiveReport(UUIDBaseModel):
    """Executive summary reports"""
    __tablename__ = "executive_reports"
    
    # Report metadata
    report_name = Column(String(255), nullable=False)
    report_type = Column(String(100), nullable=False)  # dashboard, summary, detailed
    report_category = Column(String(100))  # projects, finance, operations, strategic
    
    # Organization and creator
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Report content
    executive_summary = Column(Text)  # High-level summary
    key_metrics = Column(JSON, nullable=False)  # Key performance metrics
    health_indicators = Column(JSON, default=dict)  # Health status indicators
    
    # Analysis and insights
    trend_analysis = Column(JSON, default=dict)  # Trend analysis
    risk_analysis = Column(JSON, default=dict)   # Risk analysis
    opportunity_analysis = Column(JSON, default=dict)  # Opportunities identified
    
    # Recommendations
    recommendations = Column(JSON, default=list)  # Strategic recommendations
    action_items = Column(JSON, default=list)     # Specific action items
    decisions_required = Column(JSON, default=list)  # Decisions needed from executives
    
    # Report configuration
    data_period_start = Column(DateTime(timezone=True))
    data_period_end = Column(DateTime(timezone=True))
    report_frequency = Column(SQLEnum(ReportFrequency), default=ReportFrequency.WEEKLY)
    
    # Distribution
    target_audience = Column(JSON, default=list)  # Who should receive this report
    distribution_list = Column(JSON, default=list)  # Email distribution list
    access_permissions = Column(JSON, default=list)  # Access control
    
    # Status and generation
    is_published = Column(Boolean, default=False)
    is_automated = Column(Boolean, default=False)  # Auto-generated report
    generation_time_seconds = Column(Float)
    
    # Report generation
    report_date = Column(DateTime(timezone=True), server_default=func.now())
    next_generation_date = Column(DateTime(timezone=True))
    
    # Relationships
    organization = relationship("Organization")
    created_by = relationship("User")
    
    def __repr__(self):
        return f"<ExecutiveReport(name='{self.report_name}', type='{self.report_type}')>"


class KPIMetric(UUIDBaseModel):
    """Key Performance Indicator tracking"""
    __tablename__ = "kpi_metrics"
    
    # KPI metadata
    metric_name = Column(String(255), nullable=False)
    metric_description = Column(Text)
    metric_category = Column(String(100))  # productivity, quality, efficiency, satisfaction
    
    # Organization scope
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Metric configuration
    measurement_unit = Column(String(50))  # hours, percentage, count, currency
    target_value = Column(Float)           # Target value for the metric
    threshold_green = Column(Float)        # Green threshold
    threshold_yellow = Column(Float)       # Yellow threshold
    threshold_red = Column(Float)          # Red threshold
    
    # Current status
    current_value = Column(Float)          # Current metric value
    current_status = Column(SQLEnum(HealthStatus), default=HealthStatus.GREEN)
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    
    # Calculation method
    calculation_method = Column(String(100))  # manual, calculated, imported
    calculation_formula = Column(Text)        # Formula for calculated metrics
    data_sources = Column(JSON, default=list)  # Data sources for the metric
    
    # Historical tracking
    historical_values = Column(JSON, default=list)  # Historical values
    trend_direction = Column(String(20))             # improving, declining, stable
    trend_confidence = Column(Float)                 # Confidence in trend
    
    # Reporting settings
    is_executive_metric = Column(Boolean, default=False)  # Show in executive reports
    reporting_frequency = Column(SQLEnum(ReportFrequency), default=ReportFrequency.WEEKLY)
    alert_on_threshold = Column(Boolean, default=True)
    
    # Ownership
    metric_owner_id = Column(String, ForeignKey("users.id"))
    stakeholders = Column(JSON, default=list)  # Stakeholder user IDs
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    organization = relationship("Organization")
    created_by = relationship("User", foreign_keys=[created_by_id])
    metric_owner = relationship("User", foreign_keys=[metric_owner_id])
    
    def __repr__(self):
        return f"<KPIMetric(name='{self.metric_name}', value={self.current_value})>"
