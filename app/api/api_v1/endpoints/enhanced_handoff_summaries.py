"""Enhanced Handoff Summaries API with Auto-generation"""
from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
import json

from ....db.database import get_db
from ....models.user import User
from ....models.organization import Organization
from ....models.handoff_summary import HandoffSummary, HandoffStatus, HandoffType
from ....models.project import Project
from ....models.task import Task
from ....models.context_card import ContextCard
from ....models.decision_log import DecisionLog
from ....schemas.handoff_summary import (
    HandoffSummaryCreate, HandoffSummaryUpdate, 
    HandoffSummary as HandoffSummarySchema,
    HandoffSummaryResponse
)
from ...deps import get_current_active_user, get_current_organization

router = APIRouter()


@router.post("/auto-generate", response_model=HandoffSummaryResponse)
async def auto_generate_handoff_summary(
    project_id: str,
    to_user_id: str,
    handoff_type: HandoffType,
    task_id: Optional[str] = None,
    from_phase: Optional[str] = None,
    to_phase: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Any:
    """Auto-generate a handoff summary using AI analysis of project/task context"""
    
    # Verify project exists and belongs to organization
    project_result = await db.execute(
        select(Project).where(
            and_(
                Project.id == project_id,
                Project.organization_id == current_org.id
            )
        )
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Verify target user exists
    to_user_result = await db.execute(
        select(User).where(
            and_(
                User.id == to_user_id,
                User.organization_id == current_org.id
            )
        )
    )
    to_user = to_user_result.scalar_one_or_none()
    if not to_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found"
        )
    
    # Gather context for auto-generation
    context_data = await gather_handoff_context(
        project_id, task_id, current_user.id, db
    )
    
    # Generate handoff summary using AI analysis
    handoff_content = await generate_handoff_content(
        context_data, handoff_type, from_phase, to_phase
    )
    
    # Create the handoff summary
    handoff_summary = HandoffSummary(
        title=handoff_content["title"],
        description=handoff_content["description"],
        handoff_type=handoff_type,
        from_user_id=current_user.id,
        to_user_id=to_user_id,
        project_id=project_id,
        task_id=task_id,
        context_summary=handoff_content["context_summary"],
        key_decisions=handoff_content["key_decisions"],
        pending_actions=handoff_content["pending_actions"],
        important_notes=handoff_content["important_notes"],
        resources=handoff_content["resources"],
        skills_required=handoff_content["skills_required"],
        domain_knowledge=handoff_content["domain_knowledge"],
        stakeholder_contacts=handoff_content["stakeholder_contacts"],
        auto_generated=True,
        generation_source="ai_context_analysis",
        confidence_score=handoff_content["confidence_score"],
        context_extraction_keywords=handoff_content["extraction_keywords"],
        sentiment_analysis=handoff_content["sentiment_analysis"],
        completeness_score=handoff_content["completeness_score"],
        risk_indicators=handoff_content["risk_indicators"],
        knowledge_gaps=handoff_content["knowledge_gaps"],
        recommended_followups=handoff_content["recommended_followups"],
        priority_items=handoff_content["priority_items"]
    )
    
    db.add(handoff_summary)
    await db.commit()
    await db.refresh(handoff_summary)
    
    # Queue background task to create notification
    background_tasks.add_task(
        create_handoff_notification,
        handoff_summary.id, current_user.id, to_user_id, current_org.id, db
    )
    
    return await _enrich_handoff_response(handoff_summary, db)


@router.get("/suggestions/{project_id}")
async def get_handoff_suggestions(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get AI-powered suggestions for potential handoffs based on project activity"""
    
    # Verify project access
    project_result = await db.execute(
        select(Project).where(
            and_(
                Project.id == project_id,
                Project.organization_id == current_org.id
            )
        )
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Analyze project for handoff opportunities
    suggestions = await analyze_handoff_opportunities(project_id, current_user.id, db)
    
    return {"suggestions": suggestions}


@router.post("/{handoff_id}/enhance")
async def enhance_handoff_summary(
    handoff_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Enhance an existing handoff summary with additional AI analysis"""
    
    # Get the handoff summary
    handoff_result = await db.execute(
        select(HandoffSummary).where(HandoffSummary.id == handoff_id)
    )
    handoff = handoff_result.scalar_one_or_none()
    if not handoff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handoff summary not found"
        )
    
    # Verify access (must be from_user, to_user, or project member)
    if handoff.from_user_id != current_user.id and handoff.to_user_id != current_user.id:
        # Check if user is project member
        # TODO: Add project membership check
        pass
    
    # Re-analyze and enhance the handoff
    context_data = await gather_handoff_context(
        handoff.project_id, handoff.task_id, current_user.id, db
    )
    
    enhanced_content = await generate_handoff_content(
        context_data, handoff.handoff_type, None, None
    )
    
    # Update the handoff with enhanced content
    handoff.knowledge_gaps = enhanced_content["knowledge_gaps"]
    handoff.recommended_followups = enhanced_content["recommended_followups"]
    handoff.priority_items = enhanced_content["priority_items"]
    handoff.risk_indicators = enhanced_content["risk_indicators"]
    handoff.sentiment_analysis = enhanced_content["sentiment_analysis"]
    handoff.completeness_score = enhanced_content["completeness_score"]
    
    await db.commit()
    
    return {"message": "Handoff summary enhanced successfully"}


@router.get("/analytics/{project_id}")
async def get_handoff_analytics(
    project_id: str,
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get analytics on handoff patterns and effectiveness for a project"""
    
    period_start = datetime.utcnow() - timedelta(days=days)
    
    # Get handoffs for the period
    handoffs_query = select(HandoffSummary).where(
        and_(
            HandoffSummary.project_id == project_id,
            HandoffSummary.created_at >= period_start
        )
    )
    handoffs_result = await db.execute(handoffs_query)
    handoffs = handoffs_result.scalars().all()
    
    # Calculate analytics
    total_handoffs = len(handoffs)
    completed_handoffs = len([h for h in handoffs if h.status == HandoffStatus.COMPLETED])
    avg_completion_time = None
    
    if completed_handoffs > 0:
        completion_times = []
        for handoff in handoffs:
            if handoff.status == HandoffStatus.COMPLETED and handoff.actual_completion_date:
                delta = handoff.actual_completion_date - handoff.handoff_date
                completion_times.append(delta.total_seconds() / 3600)  # Hours
        
        if completion_times:
            avg_completion_time = sum(completion_times) / len(completion_times)
    
    # Analyze handoff types
    type_distribution = {}
    for handoff in handoffs:
        type_str = handoff.handoff_type.value
        type_distribution[type_str] = type_distribution.get(type_str, 0) + 1
    
    # Analyze completeness scores
    completeness_scores = [h.completeness_score for h in handoffs if h.completeness_score]
    avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0
    
    # Identify common knowledge gaps
    all_gaps = []
    for handoff in handoffs:
        if handoff.knowledge_gaps:
            all_gaps.extend(handoff.knowledge_gaps)
    
    from collections import Counter
    common_gaps = dict(Counter(all_gaps).most_common(5))
    
    return {
        "period_days": days,
        "total_handoffs": total_handoffs,
        "completed_handoffs": completed_handoffs,
        "completion_rate": completed_handoffs / total_handoffs if total_handoffs > 0 else 0,
        "avg_completion_time_hours": avg_completion_time,
        "avg_completeness_score": avg_completeness,
        "type_distribution": type_distribution,
        "common_knowledge_gaps": common_gaps,
        "recommendations": generate_handoff_recommendations(handoffs)
    }


# Helper functions
async def gather_handoff_context(
    project_id: str, task_id: Optional[str], user_id: str, db: AsyncSession
) -> Dict[str, Any]:
    """Gather all relevant context for handoff generation"""
    
    context = {
        "project_id": project_id,
        "task_id": task_id,
        "project_data": None,
        "task_data": None,
        "context_cards": [],
        "decision_logs": [],
        "recent_comments": [],
        "team_members": []
    }
    
    # Get project data
    project_query = select(Project).options(
        selectinload(Project.members)
    ).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if project:
        context["project_data"] = {
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "phase": getattr(project, 'current_phase', None)
        }
        context["team_members"] = [
            {"id": member.user_id, "role": member.role}
            for member in project.members
        ]
    
    # Get task data if specified
    if task_id:
        task_query = select(Task).where(Task.id == task_id)
        task_result = await db.execute(task_query)
        task = task_result.scalar_one_or_none()
        if task:
            context["task_data"] = {
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "assignee_id": task.assignee_id
            }
    
    # Get relevant context cards
    context_cards_query = select(ContextCard).where(
        or_(
            ContextCard.project_id == project_id,
            ContextCard.task_id == task_id if task_id else False
        )
    ).order_by(desc(ContextCard.created_at)).limit(10)
    
    context_cards_result = await db.execute(context_cards_query)
    context_cards = context_cards_result.scalars().all()
    context["context_cards"] = [
        {
            "title": card.title,
            "content": card.content,
            "decision_rationale": card.decision_rationale,
            "context_type": card.context_type.value,
            "tags": card.tags
        }
        for card in context_cards
    ]
    
    # Get relevant decision logs
    decision_logs_query = select(DecisionLog).where(
        DecisionLog.project_id == project_id
    ).order_by(desc(DecisionLog.created_at)).limit(5)
    
    decision_logs_result = await db.execute(decision_logs_query)
    decision_logs = decision_logs_result.scalars().all()
    context["decision_logs"] = [
        {
            "title": log.title,
            "decision_summary": log.decision_summary,
            "decision_rationale": log.decision_rationale,
            "status": log.status.value,
            "impact_level": log.impact_level.value
        }
        for log in decision_logs
    ]
    
    return context


async def generate_handoff_content(
    context_data: Dict[str, Any], 
    handoff_type: HandoffType,
    from_phase: Optional[str] = None,
    to_phase: Optional[str] = None
) -> Dict[str, Any]:
    """Generate handoff content using AI analysis (simplified implementation)"""
    
    # In a real implementation, this would use advanced NLP/AI
    # For now, we'll create a structured analysis based on the context
    
    project_data = context_data.get("project_data", {})
    task_data = context_data.get("task_data", {})
    context_cards = context_data.get("context_cards", [])
    decision_logs = context_data.get("decision_logs", [])
    
    # Generate title
    if handoff_type == HandoffType.PHASE_TRANSITION:
        title = f"Phase Transition: {from_phase} → {to_phase}"
    elif handoff_type == HandoffType.TEAM_HANDOVER:
        title = f"Team Handover: {project_data.get('name', 'Project')}"
    else:
        title = f"Handoff: {project_data.get('name', 'Project')}"
    
    # Extract key decisions
    key_decisions = []
    for decision in decision_logs:
        key_decisions.append(f"{decision['title']}: {decision['decision_summary']}")
    
    # Extract important context from context cards
    important_notes = []
    for card in context_cards:
        if card['context_type'] in ['DECISION', 'ISSUE', 'RISK']:
            important_notes.append(f"[{card['context_type']}] {card['title']}: {card['content'][:200]}...")
    
    # Generate pending actions (simplified)
    pending_actions = []
    if task_data and task_data.get('status') != 'COMPLETED':
        pending_actions.append(f"Complete task: {task_data.get('title', 'Unnamed task')}")
    
    # Identify skills and knowledge requirements
    skills_required = []
    domain_knowledge = []
    
    # Extract from context cards and decisions
    for card in context_cards:
        tags = card.get('tags', [])
        for tag in tags:
            if any(skill_word in tag.lower() for skill_word in ['skill', 'tech', 'knowledge']):
                if tag not in skills_required:
                    skills_required.append(tag)
    
    # Simple risk detection
    risk_indicators = []
    for card in context_cards:
        content_lower = card['content'].lower()
        if any(risk_word in content_lower for risk_word in ['risk', 'blocker', 'issue', 'problem']):
            risk_indicators.append(f"Risk identified: {card['title']}")
    
    # Knowledge gap analysis
    knowledge_gaps = []
    if not decision_logs:
        knowledge_gaps.append("No documented decisions found")
    if not context_cards:
        knowledge_gaps.append("Limited context documentation")
    
    # Generate recommendations
    recommended_followups = []
    if len(decision_logs) < 3:
        recommended_followups.append("Document key project decisions")
    if len(context_cards) < 5:
        recommended_followups.append("Capture more context about WHY decisions were made")
    
    # Priority items
    priority_items = []
    for decision in decision_logs:
        if decision['impact_level'] in ['HIGH', 'CRITICAL']:
            priority_items.append(f"Critical decision: {decision['title']}")
    
    # Calculate confidence and completeness scores
    confidence_score = 0.5
    if decision_logs:
        confidence_score += 0.2
    if context_cards:
        confidence_score += 0.2
    if important_notes:
        confidence_score += 0.1
    
    completeness_score = 0.3
    if key_decisions:
        completeness_score += 0.2
    if important_notes:
        completeness_score += 0.2
    if pending_actions:
        completeness_score += 0.1
    if skills_required:
        completeness_score += 0.1
    if domain_knowledge:
        completeness_score += 0.1
    
    # Sentiment analysis (simplified)
    sentiment_analysis = {
        "overall_sentiment": "neutral",
        "confidence_level": "medium",
        "complexity_level": "medium" if len(context_cards) > 3 else "low"
    }
    
    return {
        "title": title,
        "description": f"Auto-generated handoff summary for {project_data.get('name', 'project')}",
        "context_summary": f"Project: {project_data.get('name', 'Unknown')}. "
                          f"Status: {project_data.get('status', 'Unknown')}. "
                          f"Found {len(decision_logs)} key decisions and {len(context_cards)} context items.",
        "key_decisions": key_decisions,
        "pending_actions": pending_actions,
        "important_notes": important_notes,
        "resources": [],  # TODO: Extract from project/task attachments
        "skills_required": skills_required,
        "domain_knowledge": domain_knowledge,
        "stakeholder_contacts": [],  # TODO: Extract from team members
        "confidence_score": min(confidence_score, 1.0),
        "extraction_keywords": ["handoff", "transition", "transfer"],
        "sentiment_analysis": sentiment_analysis,
        "completeness_score": min(completeness_score, 1.0),
        "risk_indicators": risk_indicators,
        "knowledge_gaps": knowledge_gaps,
        "recommended_followups": recommended_followups,
        "priority_items": priority_items
    }


async def analyze_handoff_opportunities(
    project_id: str, user_id: str, db: AsyncSession
) -> List[Dict[str, Any]]:
    """Analyze project for potential handoff opportunities"""
    
    suggestions = []
    
    # TODO: Implement AI analysis for handoff opportunities
    # This would analyze:
    # - Task completion patterns
    # - User workload
    # - Skill requirements
    # - Project phases
    # - Team capacity
    
    # For now, return a simple example
    suggestions.append({
        "type": "phase_transition",
        "confidence": 0.7,
        "title": "Development to Testing Phase",
        "description": "Development tasks are nearing completion, consider handoff to testing team",
        "recommended_users": [],
        "estimated_effort": "2-3 days"
    })
    
    return suggestions


def generate_handoff_recommendations(handoffs: List[HandoffSummary]) -> List[str]:
    """Generate recommendations based on handoff analysis"""
    
    recommendations = []
    
    if len(handoffs) == 0:
        return ["No handoffs to analyze"]
    
    # Analyze completion rates
    completed = len([h for h in handoffs if h.status == HandoffStatus.COMPLETED])
    completion_rate = completed / len(handoffs)
    
    if completion_rate < 0.7:
        recommendations.append("Consider improving handoff follow-up processes")
    
    # Analyze completeness scores
    completeness_scores = [h.completeness_score for h in handoffs if h.completeness_score]
    if completeness_scores:
        avg_completeness = sum(completeness_scores) / len(completeness_scores)
        if avg_completeness < 0.6:
            recommendations.append("Focus on capturing more comprehensive handoff information")
    
    # Analyze knowledge gaps
    all_gaps = []
    for handoff in handoffs:
        if handoff.knowledge_gaps:
            all_gaps.extend(handoff.knowledge_gaps)
    
    if "No documented decisions found" in all_gaps:
        recommendations.append("Improve decision documentation practices")
    
    if "Limited context documentation" in all_gaps:
        recommendations.append("Encourage more context card creation")
    
    return recommendations


async def create_handoff_notification(
    handoff_id: str, from_user_id: str, to_user_id: str, org_id: str, db: AsyncSession
):
    """Background task to create notification about new handoff"""
    
    from ....models.notification import Notification, NotificationType, NotificationPriority
    
    notification = Notification(
        title="New Handoff Summary Received",
        message="You have received a new handoff summary that requires your review and acknowledgment.",
        notification_type=NotificationType.HANDOFF_RECEIVED,
        priority=NotificationPriority.HIGH,
        user_id=to_user_id,
        organization_id=org_id,
        handoff_summary_id=handoff_id,
        relevance_score=0.9,
        context_data={
            "handoff_id": handoff_id,
            "from_user_id": from_user_id,
            "requires_acknowledgment": True
        },
        action_required=True,
        auto_generated=True,
        source="handoff_system"
    )
    
    db.add(notification)
    await db.commit()


async def _enrich_handoff_response(handoff: HandoffSummary, db: AsyncSession) -> HandoffSummaryResponse:
    """Enrich handoff summary with related data"""
    
    # Get user names
    from_user_query = select(User).where(User.id == handoff.from_user_id)
    from_user_result = await db.execute(from_user_query)
    from_user = from_user_result.scalar_one_or_none()
    
    to_user_query = select(User).where(User.id == handoff.to_user_id)
    to_user_result = await db.execute(to_user_query)
    to_user = to_user_result.scalar_one_or_none()
    
    # Get project name
    project_query = select(Project).where(Project.id == handoff.project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    
    return HandoffSummaryResponse(
        **handoff.__dict__,
        from_user_name=f"{from_user.first_name} {from_user.last_name}" if from_user else "Unknown",
        to_user_name=f"{to_user.first_name} {to_user.last_name}" if to_user else "Unknown",
        project_name=project.name if project else "Unknown"
    )
