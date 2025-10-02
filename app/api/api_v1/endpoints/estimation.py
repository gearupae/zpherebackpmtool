"""Intelligent Time and Estimation API endpoints"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from ....api.deps_tenant import get_current_active_user_master as get_current_active_user, get_tenant_db
from ....models.user import User
from ....models.estimation import (
    TaskEstimate, EstimationHistory, TeamVelocity, EstimationTemplate,
    EffortComplexityMatrix, EstimationLearning
)
from ....schemas.estimation import (
    TaskEstimate as TaskEstimateSchema, TaskEstimateCreate, TaskEstimateUpdate,
    EstimationHistory as EstimationHistorySchema, EstimationHistoryCreate,
    TeamVelocity as TeamVelocitySchema, TeamVelocityCreate, TeamVelocityUpdate,
    EstimationTemplate as EstimationTemplateSchema, EstimationTemplateCreate, EstimationTemplateUpdate,
    EffortComplexityMatrix as EffortComplexityMatrixSchema, 
    EffortComplexityMatrixCreate, EffortComplexityMatrixUpdate,
    EstimationAccuracy, VelocityTrend, EstimationInsights, ConfidenceInterval, HistoricalPattern
)

router = APIRouter()


# Task Estimation Endpoints
@router.get("/tasks/{task_id}/estimate", response_model=TaskEstimateSchema)
async def get_task_estimate(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get estimate for a specific task"""
    stmt = select(TaskEstimate).where(TaskEstimate.task_id == task_id)
    result = await db.execute(stmt)
    estimate = result.scalar_one_or_none()
    
    if not estimate:
        # Return AI-suggested estimate if no manual estimate exists
        ai_estimate = await generate_ai_estimate(task_id, current_user, db)
        return ai_estimate
    
    return estimate


@router.post("/tasks/{task_id}/estimate", response_model=TaskEstimateSchema)
async def create_task_estimate(
    task_id: str,
    estimate_data: TaskEstimateCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create an estimate for a task"""
    if estimate_data.task_id != task_id:
        raise HTTPException(status_code=400, detail="Task ID mismatch")
    
    # Check if estimate already exists
    stmt = select(TaskEstimate).where(TaskEstimate.task_id == task_id)
    result = await db.execute(stmt)
    existing_estimate = result.scalar_one_or_none()
    
    if existing_estimate:
        raise HTTPException(status_code=400, detail="Estimate already exists for this task")
    
    # Get AI suggestion
    ai_suggestion = await calculate_ai_estimate(task_id, current_user, db)
    
    estimate = TaskEstimate(
        estimated_by_id=current_user.id,
        ai_suggested_estimate=ai_suggestion.get('estimate'),
        ai_confidence=ai_suggestion.get('confidence'),
        features_used=ai_suggestion.get('features', {}),
        **estimate_data.dict()
    )
    
    db.add(estimate)
    await db.commit()
    await db.refresh(estimate)
    
    # Create history entry
    history_entry = EstimationHistory(
        task_id=task_id,
        estimate_id=estimate.id,
        version=1,
        estimated_hours=estimate.estimated_hours or 0,
        estimator_id=current_user.id,
        estimation_date=estimate.estimation_date,
        project_context={},
        task_context={}
    )
    db.add(history_entry)
    await db.commit()
    
    return estimate


@router.put("/tasks/{task_id}/estimate", response_model=TaskEstimateSchema)
async def update_task_estimate(
    task_id: str,
    estimate_data: TaskEstimateUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a task estimate"""
    stmt = select(TaskEstimate).where(TaskEstimate.task_id == task_id)
    result = await db.execute(stmt)
    estimate = result.scalar_one_or_none()
    
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    
    # Store old values for history
    old_hours = estimate.estimated_hours
    
    # Update estimate
    for field, value in estimate_data.dict(exclude_unset=True).items():
        setattr(estimate, field, value)
    
    estimate.is_revised = True
    estimate.revision_count += 1
    
    await db.commit()
    await db.refresh(estimate)
    
    # Create history entry if hours changed
    if old_hours != estimate.estimated_hours:
        history_entry = EstimationHistory(
            task_id=task_id,
            estimate_id=estimate.id,
            version=estimate.revision_count,
            estimated_hours=estimate.estimated_hours or 0,
            estimator_id=current_user.id,
            estimation_date=func.now(),
            project_context={},
            task_context={}
        )
        db.add(history_entry)
        await db.commit()
    
    return estimate


@router.get("/tasks/{task_id}/estimation-history", response_model=List[EstimationHistorySchema])
async def get_estimation_history(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get estimation history for a task"""
    stmt = select(EstimationHistory).where(
        EstimationHistory.task_id == task_id
    ).order_by(EstimationHistory.version.desc())
    
    result = await db.execute(stmt)
    history = result.scalars().all()
    
    return history


@router.get("/estimation/confidence-interval/{task_id}", response_model=ConfidenceInterval)
async def get_confidence_interval(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get estimation confidence interval for a task"""
    stmt = select(TaskEstimate).where(TaskEstimate.task_id == task_id)
    result = await db.execute(stmt)
    estimate = result.scalar_one_or_none()
    
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    
    # Calculate confidence interval based on historical data
    confidence_data = await calculate_confidence_interval(task_id, estimate, db)
    
    return ConfidenceInterval(
        task_id=task_id,
        estimated_hours=estimate.estimated_hours or 0,
        confidence_level=estimate.confidence_level,
        lower_bound=confidence_data['lower_bound'],
        upper_bound=confidence_data['upper_bound'],
        probability_distribution=confidence_data['distribution'],
        risk_factors=confidence_data['risks']
    )


# Team Velocity Endpoints
@router.get("/teams/{team_id}/velocity", response_model=List[TeamVelocitySchema])
async def get_team_velocity(
    team_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    limit: int = Query(default=12, le=24),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Get team velocity history"""
    stmt = select(TeamVelocity).where(
        TeamVelocity.team_id == team_id,
        TeamVelocity.organization_id == current_user.organization_id
    ).order_by(TeamVelocity.period_start.desc()).offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    velocity_data = result.scalars().all()
    
    return velocity_data


@router.post("/teams/{team_id}/velocity", response_model=TeamVelocitySchema)
async def create_team_velocity(
    team_id: str,
    velocity_data: TeamVelocityCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Record team velocity for a period"""
    if velocity_data.team_id != team_id:
        raise HTTPException(status_code=400, detail="Team ID mismatch")
    
    # Calculate velocity score
    velocity_score = calculate_velocity_score(velocity_data)
    
    velocity = TeamVelocity(
        organization_id=current_user.organization_id,
        velocity_score=velocity_score,
        **velocity_data.dict()
    )
    
    db.add(velocity)
    await db.commit()
    await db.refresh(velocity)
    
    return velocity


@router.get("/teams/{team_id}/velocity-trend", response_model=VelocityTrend)
async def get_velocity_trend(
    team_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    periods: int = Query(default=6, ge=3, le=12),
) -> Any:
    """Get team velocity trend analysis"""
    stmt = select(TeamVelocity).where(
        TeamVelocity.team_id == team_id,
        TeamVelocity.organization_id == current_user.organization_id
    ).order_by(TeamVelocity.period_start.desc()).limit(periods)
    
    result = await db.execute(stmt)
    velocity_data = result.scalars().all()
    
    if not velocity_data:
        raise HTTPException(status_code=404, detail="No velocity data found")
    
    # Analyze trend
    trend_analysis = analyze_velocity_trend(velocity_data)
    
    return VelocityTrend(
        team_id=team_id,
        periods=[{
            "start": v.period_start.isoformat(),
            "end": v.period_end.isoformat(),
            "velocity": v.velocity_score,
            "story_points": v.story_points_completed,
            "hours": v.hours_logged
        } for v in velocity_data],
        avg_velocity=trend_analysis['avg_velocity'],
        velocity_trend=trend_analysis['trend'],
        trend_confidence=trend_analysis['confidence'],
        capacity_utilization=trend_analysis['utilization'],
        quality_trend=trend_analysis['quality_trend'],
        predictions=trend_analysis['predictions']
    )


# Estimation Templates Endpoints
@router.get("/estimation/templates", response_model=List[EstimationTemplateSchema])
async def get_estimation_templates(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    category: Optional[str] = Query(None),
    is_public: Optional[bool] = Query(None),
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Get estimation templates"""
    stmt = select(EstimationTemplate).where(
        EstimationTemplate.organization_id == current_user.organization_id,
        EstimationTemplate.is_active == True
    )
    
    if category:
        stmt = stmt.where(EstimationTemplate.category == category)
    
    if is_public is not None:
        stmt = stmt.where(EstimationTemplate.is_public == is_public)
    
    stmt = stmt.order_by(EstimationTemplate.avg_accuracy.desc()).offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    templates = result.scalars().all()
    
    return templates


@router.post("/estimation/templates", response_model=EstimationTemplateSchema)
async def create_estimation_template(
    template_data: EstimationTemplateCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create an estimation template"""
    template = EstimationTemplate(
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
        **template_data.dict()
    )
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    return template


# Effort Complexity Matrix Endpoints
@router.get("/estimation/complexity-matrix", response_model=List[EffortComplexityMatrixSchema])
async def get_complexity_matrices(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    is_active: bool = Query(default=True),
) -> Any:
    """Get effort complexity matrices"""
    stmt = select(EffortComplexityMatrix).where(
        EffortComplexityMatrix.organization_id == current_user.organization_id,
        EffortComplexityMatrix.is_active == is_active
    ).order_by(EffortComplexityMatrix.is_default.desc())
    
    result = await db.execute(stmt)
    matrices = result.scalars().all()
    
    return matrices


@router.post("/estimation/complexity-matrix", response_model=EffortComplexityMatrixSchema)
async def create_complexity_matrix(
    matrix_data: EffortComplexityMatrixCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create an effort complexity matrix"""
    matrix = EffortComplexityMatrix(
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
        **matrix_data.dict()
    )
    
    db.add(matrix)
    await db.commit()
    await db.refresh(matrix)
    
    return matrix


# Analytics and Insights Endpoints
@router.get("/estimation/accuracy/{user_id}", response_model=EstimationAccuracy)
async def get_estimation_accuracy(
    user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    days: int = Query(default=90, ge=30, le=365),
) -> Any:
    """Get estimation accuracy for a user"""
    # Calculate accuracy metrics
    accuracy_data = await calculate_user_accuracy(user_id, days, db)
    
    return EstimationAccuracy(
        estimator_id=user_id,
        total_estimates=accuracy_data['total'],
        accurate_estimates=accuracy_data['accurate'],
        accuracy_percentage=accuracy_data['percentage'],
        avg_variance_percentage=accuracy_data['avg_variance'],
        improvement_trend=accuracy_data['trend'],
        common_overestimation_factors=accuracy_data['over_factors'],
        common_underestimation_factors=accuracy_data['under_factors']
    )


@router.get("/estimation/insights", response_model=EstimationInsights)
async def get_estimation_insights(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    days: int = Query(default=90, ge=30, le=365),
) -> Any:
    """Get organization-wide estimation insights"""
    insights_data = await generate_estimation_insights(current_user.organization_id, days, db)
    
    return EstimationInsights(
        organization_id=current_user.organization_id,
        overall_accuracy=insights_data['accuracy'],
        top_estimators=insights_data['top_estimators'],
        accuracy_by_category=insights_data['by_category'],
        complexity_distribution=insights_data['complexity_dist'],
        estimation_bias=insights_data['bias'],
        recommendations=insights_data['recommendations'],
        ai_model_performance=insights_data['ai_performance']
    )


# Helper Functions
async def generate_ai_estimate(task_id: str, user: User, db: AsyncSession) -> TaskEstimateSchema:
    """Generate AI-powered estimate for a task"""
    # Simulate AI estimation logic
    ai_estimate = {
        'task_id': task_id,
        'estimation_method': 'historical_average',
        'estimated_hours': 8.0,
        'confidence_level': 'medium',
        'confidence_percentage': 75.0,
        'complexity_level': 'moderate',
        'ai_suggested_estimate': 8.0,
        'ai_confidence': 0.75,
        'features_used': {
            'similar_tasks': 5,
            'historical_accuracy': 0.8,
            'complexity_factors': ['medium_scope', 'known_technology']
        }
    }
    
    return TaskEstimateSchema(**ai_estimate, id='ai-generated', estimated_by_id=user.id, estimation_date=func.now())


async def calculate_ai_estimate(task_id: str, user: User, db: AsyncSession) -> dict:
    """Calculate AI estimation suggestion"""
    return {
        'estimate': 8.0,
        'confidence': 0.75,
        'features': {
            'similar_tasks': 3,
            'team_velocity': 1.2,
            'complexity_score': 0.6
        }
    }


async def calculate_confidence_interval(task_id: str, estimate: TaskEstimate, db: AsyncSession) -> dict:
    """Calculate confidence interval for an estimate"""
    base_estimate = estimate.estimated_hours or 0
    confidence = estimate.confidence_percentage or 50
    
    # Calculate bounds based on confidence and historical variance
    variance_factor = (100 - confidence) / 100
    lower_bound = base_estimate * (1 - variance_factor * 0.5)
    upper_bound = base_estimate * (1 + variance_factor * 0.5)
    
    return {
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
        'distribution': {
            'pessimistic': upper_bound,
            'optimistic': lower_bound,
            'most_likely': base_estimate
        },
        'risks': ['scope_creep', 'technical_complexity', 'external_dependencies']
    }


def calculate_velocity_score(velocity_data: TeamVelocityCreate) -> float:
    """Calculate normalized velocity score"""
    if velocity_data.team_capacity_hours and velocity_data.team_capacity_hours > 0:
        utilization = velocity_data.hours_logged / velocity_data.team_capacity_hours
        quality_factor = 1.0 - (velocity_data.rework_hours / velocity_data.hours_logged if velocity_data.hours_logged > 0 else 0)
        return min(100, utilization * quality_factor * 100)
    return 0.0


def analyze_velocity_trend(velocity_data: List[TeamVelocity]) -> dict:
    """Analyze velocity trend from historical data"""
    if len(velocity_data) < 2:
        return {
            'avg_velocity': velocity_data[0].velocity_score if velocity_data else 0,
            'trend': 'stable',
            'confidence': 0.5,
            'utilization': 0.8,
            'quality_trend': 'stable',
            'predictions': {}
        }
    
    velocities = [v.velocity_score for v in velocity_data if v.velocity_score]
    avg_velocity = sum(velocities) / len(velocities) if velocities else 0
    
    # Simple trend analysis
    recent_avg = sum(velocities[:3]) / 3 if len(velocities) >= 3 else avg_velocity
    older_avg = sum(velocities[-3:]) / 3 if len(velocities) >= 3 else avg_velocity
    
    if recent_avg > older_avg * 1.1:
        trend = 'increasing'
    elif recent_avg < older_avg * 0.9:
        trend = 'decreasing'
    else:
        trend = 'stable'
    
    return {
        'avg_velocity': avg_velocity,
        'trend': trend,
        'confidence': 0.8,
        'utilization': 0.85,
        'quality_trend': 'improving',
        'predictions': {
            'next_sprint': recent_avg * 1.05,
            'confidence': 0.7
        }
    }


async def calculate_user_accuracy(user_id: str, days: int, db: AsyncSession) -> dict:
    """Calculate estimation accuracy for a user"""
    # Simulate calculation - in real implementation, query actual data
    return {
        'total': 15,
        'accurate': 12,
        'percentage': 80.0,
        'avg_variance': 15.5,
        'trend': 'improving',
        'over_factors': ['scope_creep', 'interruptions'],
        'under_factors': ['known_patterns', 'simple_tasks']
    }


async def generate_estimation_insights(org_id: str, days: int, db: AsyncSession) -> dict:
    """Generate organization-wide estimation insights"""
    return {
        'accuracy': 78.5,
        'top_estimators': [
            {'user_id': 'user1', 'name': 'John Doe', 'accuracy': 92.3},
            {'user_id': 'user2', 'name': 'Jane Smith', 'accuracy': 88.7}
        ],
        'by_category': {
            'development': 82.1,
            'testing': 75.8,
            'design': 85.3
        },
        'complexity_dist': {
            'simple': 45,
            'moderate': 35,
            'complex': 20
        },
        'bias': {
            'overestimation': 25.0,
            'underestimation': 15.0
        },
        'recommendations': [
            'Use historical data for better estimates',
            'Break down complex tasks into smaller ones',
            'Regular calibration sessions'
        ],
        'ai_performance': {
            'accuracy': 82.5,
            'suggestions_used': 65.0
        }
    }
