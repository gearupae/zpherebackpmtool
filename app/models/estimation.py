"""Intelligent Time and Estimation Models"""
import enum
from sqlalchemy import Column, String, Text, JSON, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import UUIDBaseModel


class EstimationMethod(str, enum.Enum):
    """Estimation methods"""
    STORY_POINTS = "story_points"
    TIME_HOURS = "time_hours"
    T_SHIRT_SIZES = "t_shirt_sizes"
    PLANNING_POKER = "planning_poker"
    THREE_POINT = "three_point"
    HISTORICAL_AVERAGE = "historical_average"


class EstimationConfidence(str, enum.Enum):
    """Confidence levels for estimates"""
    VERY_LOW = "very_low"      # 0-20%
    LOW = "low"                # 20-40%
    MEDIUM = "medium"          # 40-60%
    HIGH = "high"              # 60-80%
    VERY_HIGH = "very_high"    # 80-100%


class ComplexityLevel(str, enum.Enum):
    """Task/project complexity levels"""
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class EffortCategory(str, enum.Enum):
    """Effort categorization for tasks"""
    RESEARCH = "research"
    DESIGN = "design"
    DEVELOPMENT = "development"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    DOCUMENTATION = "documentation"
    REVIEW = "review"
    MEETING = "meeting"
    PLANNING = "planning"
    BUG_FIX = "bug_fix"


class TaskEstimate(UUIDBaseModel):
    """Task estimation with intelligent learning"""
    __tablename__ = "task_estimates"
    
    # Task relationship
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, unique=True)
    
    # Estimation details
    estimation_method = Column(SQLEnum(EstimationMethod), nullable=False)
    estimated_hours = Column(Float)  # Primary estimate in hours
    story_points = Column(Integer)  # Story points if using that method
    
    # Three-point estimation (for uncertainty modeling)
    optimistic_hours = Column(Float)  # Best case scenario
    most_likely_hours = Column(Float)  # Most likely scenario
    pessimistic_hours = Column(Float)  # Worst case scenario
    
    # Confidence and complexity
    confidence_level = Column(SQLEnum(EstimationConfidence), default=EstimationConfidence.MEDIUM)
    confidence_percentage = Column(Float)  # Numeric confidence (0-100)
    complexity_level = Column(SQLEnum(ComplexityLevel), default=ComplexityLevel.MODERATE)
    
    # Effort breakdown
    effort_category = Column(SQLEnum(EffortCategory), default=EffortCategory.DEVELOPMENT)
    effort_breakdown = Column(JSON, default=dict)  # Breakdown by category
    
    # Historical data for learning
    similar_tasks = Column(JSON, default=list)  # IDs of similar tasks
    historical_accuracy = Column(Float)  # How accurate past estimates were
    adjustment_factor = Column(Float, default=1.0)  # AI adjustment based on history
    
    # Estimator information
    estimated_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    estimation_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Actual tracking for learning
    actual_hours = Column(Float)  # Actual time spent
    accuracy_percentage = Column(Float)  # How accurate this estimate was
    variance_reason = Column(Text)  # Why estimate was off if significant variance
    
    # AI/ML features
    ai_suggested_estimate = Column(Float)  # AI-suggested estimate
    ai_confidence = Column(Float)  # AI confidence in suggestion
    features_used = Column(JSON, default=dict)  # Features used for AI estimation
    
    # Status
    is_final = Column(Boolean, default=False)  # Is this the final estimate?
    is_revised = Column(Boolean, default=False)  # Has this been revised?
    revision_count = Column(Integer, default=0)
    
    # Relationships
    task = relationship("Task")
    estimated_by = relationship("User")
    
    def __repr__(self):
        return f"<TaskEstimate(task_id='{self.task_id}', hours={self.estimated_hours})>"


class EstimationHistory(UUIDBaseModel):
    """Historical estimation data for learning"""
    __tablename__ = "estimation_history"
    
    # Task and estimate relationships
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    estimate_id = Column(String, ForeignKey("task_estimates.id"), nullable=False)
    
    # Historical record
    version = Column(Integer, nullable=False)  # Version of the estimate
    estimated_hours = Column(Float, nullable=False)
    actual_hours = Column(Float)
    
    # Context at time of estimation
    estimator_id = Column(String, ForeignKey("users.id"), nullable=False)
    estimation_date = Column(DateTime(timezone=True), nullable=False)
    project_context = Column(JSON, default=dict)  # Project state when estimated
    task_context = Column(JSON, default=dict)  # Task details when estimated
    
    # Learning metrics
    accuracy_score = Column(Float)  # How accurate this estimate was
    factors_that_helped = Column(JSON, default=list)  # What made this accurate
    factors_that_hindered = Column(JSON, default=list)  # What made this inaccurate
    
    # Relationships
    task = relationship("Task")
    estimate = relationship("TaskEstimate")
    estimator = relationship("User")
    
    def __repr__(self):
        return f"<EstimationHistory(task_id='{self.task_id}', version={self.version})>"


class TeamVelocity(UUIDBaseModel):
    """Team velocity tracking for capacity planning"""
    __tablename__ = "team_velocity"
    
    # Team and time period
    team_id = Column(String, nullable=False)  # Can be project team or org team
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    
    # Velocity metrics
    story_points_completed = Column(Integer, default=0)
    hours_logged = Column(Float, default=0.0)
    tasks_completed = Column(Integer, default=0)
    
    # Capacity metrics
    team_capacity_hours = Column(Float)  # Available team hours for period
    utilization_percentage = Column(Float)  # Actual vs capacity
    velocity_score = Column(Float)  # Normalized velocity score
    
    # Quality metrics
    bugs_introduced = Column(Integer, default=0)
    rework_hours = Column(Float, default=0.0)
    quality_score = Column(Float)  # Quality metric (0-100)
    
    # Team composition
    team_members = Column(JSON, default=list)  # Team member IDs
    team_size = Column(Integer)
    avg_experience_level = Column(Float)  # Average team experience
    
    # Context factors
    period_type = Column(String(20), default="sprint")  # sprint, month, quarter
    interruptions = Column(JSON, default=list)  # Interruptions during period
    environment_factors = Column(JSON, default=dict)  # Factors affecting velocity
    
    # Trends
    velocity_trend = Column(String(20))  # increasing, decreasing, stable
    trend_confidence = Column(Float)  # Confidence in trend assessment
    
    # Relationships
    organization = relationship("Organization")
    
    def __repr__(self):
        return f"<TeamVelocity(team_id='{self.team_id}', velocity={self.velocity_score})>"


class EstimationTemplate(UUIDBaseModel):
    """Templates for common estimation scenarios"""
    __tablename__ = "estimation_templates"
    
    # Template metadata
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))  # e.g., 'bug_fix', 'feature', 'research'
    
    # Organization and creator
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Template content
    base_estimate_hours = Column(Float)
    complexity_multipliers = Column(JSON, default=dict)  # Multipliers by complexity
    effort_breakdown = Column(JSON, default=dict)  # Standard effort breakdown
    
    # Estimation factors
    typical_factors = Column(JSON, default=list)  # Common factors to consider
    risk_factors = Column(JSON, default=list)  # Risk factors that increase estimates
    efficiency_factors = Column(JSON, default=list)  # Factors that decrease estimates
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    avg_accuracy = Column(Float)  # Average accuracy of estimates using this template
    
    # Template settings
    is_public = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    organization = relationship("Organization")
    created_by = relationship("User")
    
    def __repr__(self):
        return f"<EstimationTemplate(name='{self.name}', category='{self.category}')>"


class EffortComplexityMatrix(UUIDBaseModel):
    """Effort vs Complexity matrix for visual estimation"""
    __tablename__ = "effort_complexity_matrix"
    
    # Matrix metadata
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Organization
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Matrix configuration
    effort_levels = Column(JSON, nullable=False)  # Effort level definitions
    complexity_levels = Column(JSON, nullable=False)  # Complexity level definitions
    matrix_cells = Column(JSON, nullable=False)  # Cell definitions with estimates
    
    # Scoring rules
    scoring_rules = Column(JSON, default=dict)  # Rules for assigning tasks to cells
    auto_assignment = Column(Boolean, default=False)  # Auto-assign tasks to matrix
    
    # Usage and effectiveness
    tasks_categorized = Column(Integer, default=0)
    avg_estimation_accuracy = Column(Float)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # Relationships
    organization = relationship("Organization")
    created_by = relationship("User")
    
    def __repr__(self):
        return f"<EffortComplexityMatrix(name='{self.name}', org='{self.organization_id}')>"


class EstimationLearning(UUIDBaseModel):
    """Machine learning model for estimation accuracy"""
    __tablename__ = "estimation_learning"
    
    # Model metadata
    model_name = Column(String(255), nullable=False)
    model_version = Column(String(50), nullable=False)
    
    # Organization scope
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    
    # Model data
    training_data_count = Column(Integer, default=0)
    model_accuracy = Column(Float)  # Model accuracy percentage
    model_features = Column(JSON, default=list)  # Features used in model
    model_parameters = Column(JSON, default=dict)  # Model parameters/weights
    
    # Training information
    last_trained = Column(DateTime(timezone=True))
    training_duration_minutes = Column(Float)
    validation_score = Column(Float)
    
    # Performance metrics
    mean_absolute_error = Column(Float)
    root_mean_square_error = Column(Float)
    r_squared = Column(Float)
    
    # Model status
    is_active = Column(Boolean, default=True)
    is_production = Column(Boolean, default=False)
    
    # Relationships
    organization = relationship("Organization")
    
    def __repr__(self):
        return f"<EstimationLearning(name='{self.model_name}', accuracy={self.model_accuracy})>"
