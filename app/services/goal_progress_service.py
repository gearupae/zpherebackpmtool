import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..db.database import get_db
from ..models.goal import Goal, GoalProgress, GoalStatus, GoalType
from ..models.user import User
from ..models.item import Item  # Assuming there's an Item model for products
from ..models.project_invoice import ProjectInvoice  # Assuming there's an invoice model

logger = logging.getLogger(__name__)

class GoalProgressService:
    """Service for automatic goal progress tracking"""
    
    def __init__(self):
        pass
    
    async def update_sales_goals_progress(self, db: Session):
        """Update progress for sales-type goals based on actual sales data"""
        logger.info("Updating sales goals progress...")
        
        try:
            # Find all active sales goals with auto-update enabled
            sales_goals = db.query(Goal).filter(
                and_(
                    Goal.goal_type == GoalType.SALES,
                    Goal.auto_update_progress == True,
                    Goal.status.in_([GoalStatus.NOT_STARTED, GoalStatus.IN_PROGRESS]),
                    Goal.is_archived == False
                )
            ).all()
            
            logger.info(f"Found {len(sales_goals)} sales goals to update")
            
            for goal in sales_goals:
                try:
                    await self.update_individual_sales_goal(db, goal)
                except Exception as e:
                    logger.error(f"Error updating sales goal {goal.id}: {e}")
                    continue
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating sales goals progress: {e}")
            db.rollback()
    
    async def update_individual_sales_goal(self, db: Session, goal: Goal):
        """Update progress for an individual sales goal"""
        
        # Calculate current sales value based on goal metadata and unit
        current_value = 0.0
        
        if goal.unit and getattr(goal, 'meta', None):
            # Check if this is a product-specific goal
            if 'product_filter' in goal.meta:
                current_value = await self.calculate_product_sales(db, goal)
            elif 'revenue_based' in goal.meta and goal.meta['revenue_based']:
                current_value = await self.calculate_revenue_progress(db, goal)
            else:
                # Generic sales goal - calculate based on invoices or orders
                current_value = await self.calculate_general_sales(db, goal)
        
        # Only update if the value has changed
        if current_value != goal.current_value:
            previous_value = goal.current_value
            
            # Create progress log
            progress_log = GoalProgress(
                goal_id=goal.id,
                previous_value=previous_value,
                new_value=current_value,
                change_amount=current_value - previous_value,
                notes=f"Automatic update from sales data",
                source="automatic",
                created_by=goal.created_by  # Use goal creator as the updater
            )
            
            # Update goal current value and completion percentage
            goal.current_value = current_value
            goal.completion_percentage = goal.calculate_completion_percentage()
            
            # Update goal status based on completion
            if goal.completion_percentage >= 100 and goal.status != GoalStatus.COMPLETED:
                goal.status = GoalStatus.COMPLETED
            elif goal.completion_percentage > 0 and goal.status == GoalStatus.NOT_STARTED:
                goal.status = GoalStatus.IN_PROGRESS
            
            db.add(progress_log)
            
            logger.info(f"Updated sales goal {goal.id}: {previous_value} -> {current_value}")
    
    async def calculate_product_sales(self, db: Session, goal: Goal) -> float:
        """Calculate sales progress for product-specific goals"""
        try:
            product_filter = (goal.meta or {}).get('product_filter', {})
            
            # This would depend on your actual data model
            # For now, I'll provide a template structure
            
            if 'product_ids' in product_filter:
                # Count sales for specific products
                product_ids = product_filter['product_ids']
                # TODO: Query your sales/order tables to get quantity sold
                # Example:
                # sales = db.query(OrderItem).join(Order).filter(
                #     OrderItem.product_id.in_(product_ids),
                #     Order.created_at >= goal.start_date,
                #     Order.created_at <= datetime.now(timezone.utc)
                # ).all()
                # return sum(item.quantity for item in sales)
                
            elif 'product_categories' in product_filter:
                # Count sales for product categories
                categories = product_filter['product_categories']
                # TODO: Implement category-based calculation
                
            return 0.0  # Placeholder
            
        except Exception as e:
            logger.error(f"Error calculating product sales for goal {goal.id}: {e}")
            return goal.current_value  # Return current value if calculation fails
    
    async def calculate_revenue_progress(self, db: Session, goal: Goal) -> float:
        """Calculate revenue-based goal progress"""
        try:
            # Calculate revenue within the goal period
            revenue_query = db.query(ProjectInvoice).filter(
                and_(
                    ProjectInvoice.created_at >= goal.start_date,
                    ProjectInvoice.created_at <= datetime.now(timezone.utc),
                    ProjectInvoice.status == 'paid'  # Only count paid invoices
                )
            )
            
            # Filter by organization if goal is organization-specific
            if goal.organization_id:
                # Assuming invoices have organization context
                # revenue_query = revenue_query.filter(ProjectInvoice.organization_id == goal.organization_id)
                pass
            
            # Filter by team members if goal is team-specific
            if goal.members:
                member_ids = [member.id for member in goal.members]
                # revenue_query = revenue_query.filter(ProjectInvoice.created_by.in_(member_ids))
                pass
            
            invoices = revenue_query.all()
            total_revenue = sum(invoice.amount for invoice in invoices if invoice.amount)
            
            return float(total_revenue)
            
        except Exception as e:
            logger.error(f"Error calculating revenue progress for goal {goal.id}: {e}")
            return goal.current_value
    
    async def calculate_general_sales(self, db: Session, goal: Goal) -> float:
        """Calculate general sales progress"""
        try:
            # This is a fallback method for goals without specific filters
            # You might calculate based on:
            # - Total number of completed projects
            # - Total number of customers acquired
            # - Total revenue generated
            
            # For now, return current value as placeholder
            return goal.current_value
            
        except Exception as e:
            logger.error(f"Error calculating general sales for goal {goal.id}: {e}")
            return goal.current_value
    
    async def update_project_goals_progress(self, db: Session):
        """Update progress for project-type goals"""
        logger.info("Updating project goals progress...")
        
        try:
            project_goals = db.query(Goal).filter(
                and_(
                    Goal.goal_type == GoalType.PROJECT,
                    Goal.auto_update_progress == True,
                    Goal.status.in_([GoalStatus.NOT_STARTED, GoalStatus.IN_PROGRESS]),
                    Goal.is_archived == False,
                    Goal.project_id.isnot(None)  # Must be associated with a project
                )
            ).all()
            
            logger.info(f"Found {len(project_goals)} project goals to update")
            
            for goal in project_goals:
                try:
                    await self.update_individual_project_goal(db, goal)
                except Exception as e:
                    logger.error(f"Error updating project goal {goal.id}: {e}")
                    continue
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating project goals progress: {e}")
            db.rollback()
    
    async def update_individual_project_goal(self, db: Session, goal: Goal):
        """Update progress for an individual project goal"""
        try:
            # Get the associated project
            from ..models.project import Project
            project = db.query(Project).filter(Project.id == goal.project_id).first()
            
            if not project:
                logger.warning(f"Project {goal.project_id} not found for goal {goal.id}")
                return
            
            # Calculate progress based on project completion
            # This depends on how you track project progress in your system
            current_value = 0.0
            
            if hasattr(project, 'completion_percentage'):
                current_value = float(project.completion_percentage)
            elif hasattr(project, 'status'):
                # Map project status to percentage
                status_map = {
                    'planning': 10.0,
                    'active': 50.0,
                    'completed': 100.0,
                    'on_hold': 0.0,
                    'cancelled': 0.0
                }
                current_value = status_map.get(project.status, 0.0)
            
            # Update goal if value changed
            if current_value != goal.current_value:
                previous_value = goal.current_value
                
                progress_log = GoalProgress(
                    goal_id=goal.id,
                    previous_value=previous_value,
                    new_value=current_value,
                    change_amount=current_value - previous_value,
                    notes=f"Automatic update from project {project.name} progress",
                    source="automatic",
                    reference_id=goal.project_id,
                    created_by=goal.created_by
                )
                
                goal.current_value = current_value
                goal.completion_percentage = current_value  # For project goals, current value IS the percentage
                
                # Update status
                if goal.completion_percentage >= 100:
                    goal.status = GoalStatus.COMPLETED
                elif goal.completion_percentage > 0 and goal.status == GoalStatus.NOT_STARTED:
                    goal.status = GoalStatus.IN_PROGRESS
                
                db.add(progress_log)
                logger.info(f"Updated project goal {goal.id}: {previous_value}% -> {current_value}%")
            
        except Exception as e:
            logger.error(f"Error updating individual project goal {goal.id}: {e}")
    
    async def trigger_goal_progress_update(self, db: Session, goal_id: str, new_value: float, source: str = "manual", reference_id: Optional[str] = None, notes: Optional[str] = None):
        """Manually trigger a goal progress update"""
        try:
            goal = db.query(Goal).filter(Goal.id == goal_id).first()
            if not goal:
                raise ValueError(f"Goal {goal_id} not found")
            
            previous_value = goal.current_value
            
            # Create progress log
            progress_log = GoalProgress(
                goal_id=goal_id,
                previous_value=previous_value,
                new_value=new_value,
                change_amount=new_value - previous_value,
                notes=notes or f"Manual update via {source}",
                source=source,
                reference_id=reference_id,
                created_by=goal.created_by  # This should be passed from the API
            )
            
            # Update goal
            goal.current_value = new_value
            goal.completion_percentage = goal.calculate_completion_percentage()
            
            # Update status
            if goal.completion_percentage >= 100 and goal.status != GoalStatus.COMPLETED:
                goal.status = GoalStatus.COMPLETED
            elif goal.completion_percentage > 0 and goal.status == GoalStatus.NOT_STARTED:
                goal.status = GoalStatus.IN_PROGRESS
            
            db.add(progress_log)
            db.commit()
            
            logger.info(f"Manually updated goal {goal_id}: {previous_value} -> {new_value}")
            
            return progress_log
            
        except Exception as e:
            logger.error(f"Error manually updating goal {goal_id}: {e}")
            db.rollback()
            raise
    
    def calculate_achievement_probability(self, goal: Goal) -> float:
        """Enhanced probability calculation with more factors"""
        try:
            now = datetime.now(timezone.utc)
            
            # Basic time and completion factors
            total_duration = (goal.end_date - goal.start_date).total_seconds()
            elapsed_time = (now - goal.start_date).total_seconds()
            remaining_time = (goal.end_date - now).total_seconds()
            
            if remaining_time <= 0:
                return 0.0 if goal.completion_percentage < 100 else 100.0
            
            if total_duration <= 0:
                return goal.completion_percentage
            
            time_progress = elapsed_time / total_duration
            completion_progress = goal.completion_percentage / 100.0
            
            # Calculate base probability
            if time_progress == 0:
                base_probability = completion_progress
            else:
                progress_rate = completion_progress / time_progress
                base_probability = min(1.0, progress_rate * completion_progress)
            
            # Apply modifiers based on goal characteristics
            probability = base_probability
            
            # Historical performance modifier (if you have historical data)
            # This could be based on the user's or team's past goal completion rates
            
            # Goal complexity modifier
            if hasattr(goal, 'meta') and goal.meta:
                complexity_score = goal.meta.get('complexity', 1.0)
                probability *= (2.0 - complexity_score)  # Higher complexity reduces probability
            
            # Team size modifier (more people might increase chances)
            if goal.members:
                team_factor = min(1.2, 1.0 + (len(goal.members) - 1) * 0.05)  # Max 20% boost
                probability *= team_factor
            
            # Recent activity modifier
            if hasattr(goal, 'progress_logs') and goal.progress_logs:
                recent_logs = [log for log in goal.progress_logs 
                             if (now - log.created_at).days <= 7]
                if recent_logs:
                    probability *= 1.1  # 10% boost for recent activity
            
            # Checklist completion modifier
            if goal.checklists:
                checklist_completion = sum(1 for item in goal.checklists if item.is_completed) / len(goal.checklists)
                probability = (probability + checklist_completion) / 2  # Average with checklist progress
            
            return max(0.0, min(100.0, probability * 100))
            
        except Exception as e:
            logger.error(f"Error calculating achievement probability for goal {goal.id}: {e}")
            return goal.get_probability_of_achievement()  # Fallback to basic calculation

# Global service instance
goal_progress_service = GoalProgressService()
