"""Knowledge Base Integration Service for Auto-linking and Smart Recommendations"""
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.orm import selectinload
import re
import json
from datetime import datetime, timedelta

from ..models.knowledge_base import KnowledgeArticle, KnowledgeLink, KnowledgeStatus
from ..models.context_card import ContextCard
from ..models.decision_log import DecisionLog
from ..models.handoff_summary import HandoffSummary
from ..models.task import Task
from ..models.project import Project
from ..models.notification import Notification, NotificationType, NotificationPriority


class KnowledgeIntegrationService:
    """Service for intelligent knowledge integration and auto-linking"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def auto_link_task_to_knowledge(
        self, task_id: str, user_id: str, org_id: str
    ) -> List[Dict[str, Any]]:
        """Auto-link a task to relevant knowledge base articles and context"""
        
        # Get task details
        task = await self._get_task_with_context(task_id)
        if not task:
            return []
        
        # Find relevant knowledge
        relevant_articles = await self._find_relevant_articles(task)
        relevant_context_cards = await self._find_relevant_context_cards(task)
        relevant_decisions = await self._find_relevant_decisions(task)
        
        # Create knowledge links
        links_created = []
        
        # Link articles
        for article, relevance_score in relevant_articles:
            link = await self._create_knowledge_link(
                article.id, task_id, "task", "references", 
                relevance_score, user_id, auto_generated=True
            )
            if link:
                links_created.append({
                    "type": "article",
                    "id": article.id,
                    "title": article.title,
                    "relevance_score": relevance_score,
                    "link_type": "references"
                })
        
        # Link context cards
        for card, relevance_score in relevant_context_cards:
            links_created.append({
                "type": "context_card",
                "id": card.id,
                "title": card.title,
                "relevance_score": relevance_score,
                "link_type": "provides_context"
            })
        
        # Link decisions
        for decision, relevance_score in relevant_decisions:
            links_created.append({
                "type": "decision",
                "id": decision.id,
                "title": decision.title,
                "relevance_score": relevance_score,
                "link_type": "influences"
            })
        
        # Create notification if significant links found
        if len(links_created) >= 2:
            await self._create_knowledge_notification(
                task_id, user_id, org_id, links_created
            )
        
        return links_created
    
    async def suggest_knowledge_for_task(
        self, task_id: str, limit: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get knowledge suggestions for a task without creating links"""
        
        task = await self._get_task_with_context(task_id)
        if not task:
            return {"articles": [], "context_cards": [], "decisions": []}
        
        # Find relevant knowledge
        relevant_articles = await self._find_relevant_articles(task, limit=limit)
        relevant_context_cards = await self._find_relevant_context_cards(task, limit=limit)
        relevant_decisions = await self._find_relevant_decisions(task, limit=limit)
        
        return {
            "articles": [
                {
                    "id": article.id,
                    "title": article.title,
                    "summary": article.summary,
                    "knowledge_type": article.knowledge_type.value,
                    "relevance_score": score,
                    "view_count": article.view_count
                }
                for article, score in relevant_articles
            ],
            "context_cards": [
                {
                    "id": card.id,
                    "title": card.title,
                    "content_preview": card.content[:200] + "..." if len(card.content) > 200 else card.content,
                    "context_type": card.context_type.value,
                    "relevance_score": score,
                    "auto_captured": card.auto_captured
                }
                for card, score in relevant_context_cards
            ],
            "decisions": [
                {
                    "id": decision.id,
                    "title": decision.title,
                    "decision_summary": decision.decision_summary,
                    "impact_level": decision.impact_level.value,
                    "relevance_score": score,
                    "decision_date": decision.decision_date.isoformat()
                }
                for decision, score in relevant_decisions
            ]
        }
    
    async def auto_capture_knowledge_from_project_activity(
        self, project_id: str, activity_type: str, activity_data: Dict[str, Any],
        user_id: str, org_id: str
    ) -> List[Dict[str, Any]]:
        """Auto-capture knowledge from project activities"""
        
        captured_items = []
        
        # Analyze activity for knowledge capture opportunities
        if activity_type == "task_completion":
            captured_items.extend(
                await self._capture_from_task_completion(
                    activity_data, project_id, user_id, org_id
                )
            )
        
        elif activity_type == "milestone_reached":
            captured_items.extend(
                await self._capture_from_milestone(
                    activity_data, project_id, user_id, org_id
                )
            )
        
        elif activity_type == "phase_transition":
            captured_items.extend(
                await self._capture_from_phase_transition(
                    activity_data, project_id, user_id, org_id
                )
            )
        
        return captured_items
    
    async def generate_knowledge_recommendations(
        self, user_id: str, org_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Generate personalized knowledge recommendations"""
        
        # Get user's recent activity
        user_activity = await self._get_user_activity(user_id, days)
        
        # Analyze activity patterns
        activity_analysis = await self._analyze_activity_patterns(user_activity)
        
        # Generate recommendations
        recommendations = {
            "trending_articles": await self._get_trending_articles(org_id, limit=5),
            "related_to_activity": await self._get_activity_related_knowledge(activity_analysis, limit=5),
            "knowledge_gaps": await self._identify_knowledge_gaps(user_activity),
            "suggested_context_cards": await self._suggest_context_card_creation(user_activity),
            "decision_follow_ups": await self._get_decision_follow_ups(user_id, org_id)
        }
        
        return recommendations
    
    async def update_knowledge_relevance_scores(self, org_id: str) -> Dict[str, int]:
        """Update relevance scores based on usage patterns"""
        
        updated_counts = {
            "articles": 0,
            "context_cards": 0,
            "decisions": 0
        }
        
        # Update article relevance based on views and links
        articles_query = select(KnowledgeArticle).where(
            KnowledgeArticle.organization_id == org_id
        )
        articles_result = await self.db.execute(articles_query)
        articles = articles_result.scalars().all()
        
        for article in articles:
            # Calculate new relevance score based on:
            # - View count
            # - Recent views
            # - Links to other content
            # - User ratings
            new_score = await self._calculate_article_relevance(article)
            if abs(new_score - (article.helpful_votes / max(article.view_count, 1))) > 0.1:
                # Update if significant change
                updated_counts["articles"] += 1
        
        await self.db.commit()
        return updated_counts
    
    # Private helper methods
    
    async def _get_task_with_context(self, task_id: str) -> Optional[Task]:
        """Get task with all related context"""
        query = select(Task).options(
            selectinload(Task.project),
            selectinload(Task.assignee),
            selectinload(Task.context_cards)
        ).where(Task.id == task_id)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _find_relevant_articles(
        self, task: Task, limit: int = 5
    ) -> List[Tuple[KnowledgeArticle, float]]:
        """Find relevant knowledge base articles for a task"""
        
        # Extract keywords from task
        keywords = self._extract_keywords(
            f"{task.title} {task.description or ''}"
        )
        
        if not keywords:
            return []
        
        # Search for articles using text similarity
        search_text = " ".join(keywords)
        
        # Use PostgreSQL full-text search (simplified)
        query = select(KnowledgeArticle).where(
            and_(
                KnowledgeArticle.status == KnowledgeStatus.PUBLISHED,
                or_(
                    KnowledgeArticle.title.ilike(f"%{search_text}%"),
                    KnowledgeArticle.content.ilike(f"%{search_text}%"),
                    KnowledgeArticle.summary.ilike(f"%{search_text}%")
                )
            )
        ).order_by(
            KnowledgeArticle.view_count.desc(),
            KnowledgeArticle.helpful_votes.desc()
        ).limit(limit)
        
        result = await self.db.execute(query)
        articles = result.scalars().all()
        
        # Calculate relevance scores
        relevant_articles = []
        for article in articles:
            score = self._calculate_text_similarity(
                f"{task.title} {task.description or ''}", 
                f"{article.title} {article.summary or ''}"
            )
            if score > 0.3:  # Minimum relevance threshold
                relevant_articles.append((article, score))
        
        return sorted(relevant_articles, key=lambda x: x[1], reverse=True)
    
    async def _find_relevant_context_cards(
        self, task: Task, limit: int = 5
    ) -> List[Tuple[ContextCard, float]]:
        """Find relevant context cards for a task"""
        
        # Look for context cards in the same project or related projects
        query = select(ContextCard).where(
            and_(
                ContextCard.project_id == task.project_id,
                ContextCard.is_active == True,
                ContextCard.is_archived == False
            )
        ).order_by(ContextCard.created_at.desc()).limit(limit * 2)
        
        result = await self.db.execute(query)
        context_cards = result.scalars().all()
        
        # Calculate relevance scores
        relevant_cards = []
        task_text = f"{task.title} {task.description or ''}"
        
        for card in context_cards:
            card_text = f"{card.title} {card.content}"
            score = self._calculate_text_similarity(task_text, card_text)
            
            # Boost score for certain context types
            if card.context_type.value in ['DECISION', 'ISSUE']:
                score += 0.1
            
            if score > 0.2:
                relevant_cards.append((card, score))
        
        return sorted(relevant_cards, key=lambda x: x[1], reverse=True)[:limit]
    
    async def _find_relevant_decisions(
        self, task: Task, limit: int = 5
    ) -> List[Tuple[DecisionLog, float]]:
        """Find relevant decision logs for a task"""
        
        query = select(DecisionLog).where(
            DecisionLog.project_id == task.project_id
        ).order_by(DecisionLog.decision_date.desc()).limit(limit * 2)
        
        result = await self.db.execute(query)
        decisions = result.scalars().all()
        
        # Calculate relevance scores
        relevant_decisions = []
        task_text = f"{task.title} {task.description or ''}"
        
        for decision in decisions:
            decision_text = f"{decision.title} {decision.decision_summary} {decision.problem_statement}"
            score = self._calculate_text_similarity(task_text, decision_text)
            
            # Boost score for high-impact decisions
            if decision.impact_level.value in ['HIGH', 'CRITICAL']:
                score += 0.15
            
            if score > 0.25:
                relevant_decisions.append((decision, score))
        
        return sorted(relevant_decisions, key=lambda x: x[1], reverse=True)[:limit]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text"""
        if not text:
            return []
        
        # Simple keyword extraction (in production, use proper NLP)
        text = text.lower()
        
        # Remove common words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
        }
        
        # Extract words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        keywords = [word for word in words if word not in stop_words]
        
        # Return unique keywords
        return list(set(keywords))
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (simplified Jaccard similarity)"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(self._extract_keywords(text1))
        words2 = set(self._extract_keywords(text2))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    async def _create_knowledge_link(
        self, article_id: str, entity_id: str, entity_type: str,
        link_type: str, relevance_score: float, user_id: str, auto_generated: bool = False
    ) -> Optional[KnowledgeLink]:
        """Create a knowledge link between article and entity"""
        
        try:
            link = KnowledgeLink(
                article_id=article_id,
                link_type=link_type,
                relevance_score=int(relevance_score * 10),  # Scale to 1-10
                created_by_id=user_id,
                auto_generated=auto_generated,
                confidence_score="high" if relevance_score > 0.7 else "medium" if relevance_score > 0.4 else "low"
            )
            
            # Set the appropriate foreign key based on entity type
            if entity_type == "task":
                link.task_id = entity_id
            elif entity_type == "project":
                link.project_id = entity_id
            elif entity_type == "decision":
                link.decision_id = entity_id
            elif entity_type == "context_card":
                link.context_card_id = entity_id
            
            self.db.add(link)
            await self.db.commit()
            return link
            
        except Exception as e:
            await self.db.rollback()
            return None
    
    async def _create_knowledge_notification(
        self, task_id: str, user_id: str, org_id: str, links_created: List[Dict[str, Any]]
    ):
        """Create notification about knowledge links"""
        
        from .notification_service import create_notification_for_user
        await create_notification_for_user(
            self.db,
            user_id=user_id,
            org_id=org_id,
            title="Relevant Knowledge Found",
            message=f"We found {len(links_created)} relevant knowledge items for your task.",
            notification_type=NotificationType.KNOWLEDGE_ARTICLE_SHARED,
            priority=NotificationPriority.NORMAL,
            task_id=task_id,
            relevance_score=0.7,
            context_data={
                "links_created": links_created,
                "auto_generated": True
            },
            action_required=False,
            auto_generated=True,
            source="knowledge_integration",
        )
    
    async def _capture_from_task_completion(
        self, activity_data: Dict[str, Any], project_id: str, user_id: str, org_id: str
    ) -> List[Dict[str, Any]]:
        """Capture knowledge from task completion"""
        captured_items = []
        
        # TODO: Analyze task completion for lessons learned
        # - What worked well?
        # - What could be improved?
        # - What knowledge was gained?
        
        return captured_items
    
    async def _capture_from_milestone(
        self, activity_data: Dict[str, Any], project_id: str, user_id: str, org_id: str
    ) -> List[Dict[str, Any]]:
        """Capture knowledge from milestone completion"""
        captured_items = []
        
        # TODO: Analyze milestone for knowledge capture
        # - Key achievements
        # - Challenges overcome
        # - Process improvements
        
        return captured_items
    
    async def _capture_from_phase_transition(
        self, activity_data: Dict[str, Any], project_id: str, user_id: str, org_id: str
    ) -> List[Dict[str, Any]]:
        """Capture knowledge from phase transitions"""
        captured_items = []
        
        # TODO: Analyze phase transition for knowledge capture
        # - Phase summary
        # - Key decisions made
        # - Lessons learned
        # - Handoff information
        
        return captured_items
    
    async def _get_user_activity(self, user_id: str, days: int) -> Dict[str, Any]:
        """Get user's recent activity for analysis"""
        period_start = datetime.utcnow() - timedelta(days=days)
        
        # Get tasks worked on
        tasks_query = select(Task).where(
            and_(
                Task.assignee_id == user_id,
                Task.updated_at >= period_start
            )
        )
        tasks_result = await self.db.execute(tasks_query)
        tasks = tasks_result.scalars().all()
        
        # Get context cards created
        cards_query = select(ContextCard).where(
            and_(
                ContextCard.created_by_id == user_id,
                ContextCard.created_at >= period_start
            )
        )
        cards_result = await self.db.execute(cards_query)
        cards = cards_result.scalars().all()
        
        return {
            "tasks": tasks,
            "context_cards": cards,
            "period_days": days
        }
    
    async def _analyze_activity_patterns(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user activity patterns"""
        # TODO: Implement activity pattern analysis
        return {
            "primary_domains": [],
            "skill_areas": [],
            "project_types": []
        }
    
    async def _get_trending_articles(self, org_id: str, limit: int) -> List[Dict[str, Any]]:
        """Get trending knowledge articles"""
        # TODO: Implement trending algorithm based on recent views
        return []
    
    async def _get_activity_related_knowledge(
        self, activity_analysis: Dict[str, Any], limit: int
    ) -> List[Dict[str, Any]]:
        """Get knowledge related to user's activity"""
        # TODO: Implement activity-based recommendations
        return []
    
    async def _identify_knowledge_gaps(self, activity: Dict[str, Any]) -> List[str]:
        """Identify potential knowledge gaps based on activity"""
        # TODO: Implement knowledge gap analysis
        return []
    
    async def _suggest_context_card_creation(self, activity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Suggest context card creation opportunities"""
        # TODO: Implement context card suggestions
        return []
    
    async def _get_decision_follow_ups(self, user_id: str, org_id: str) -> List[Dict[str, Any]]:
        """Get decisions that need follow-up"""
        # TODO: Implement decision follow-up recommendations
        return []
    
    async def _calculate_article_relevance(self, article: KnowledgeArticle) -> float:
        """Calculate article relevance score"""
        # TODO: Implement sophisticated relevance calculation
        return 0.5
