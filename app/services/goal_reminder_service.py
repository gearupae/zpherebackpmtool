import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..db.database import get_db
from ..models.goal import Goal, GoalReminder, GoalStatus
from ..models.user import User
from ..models.notification import Notification
from ..core.config import settings

logger = logging.getLogger(__name__)

class GoalReminderService:
    """Service for processing goal reminders and sending notifications"""
    
    def __init__(self):
        self.is_running = False
    
    async def start_reminder_scheduler(self):
        """Start the reminder scheduler background task"""
        if self.is_running:
            logger.warning("Goal reminder scheduler is already running")
            return
        
        self.is_running = True
        logger.info("Starting goal reminder scheduler...")
        
        while self.is_running:
            try:
                await self.process_due_reminders()
                # Check for reminders every 5 minutes
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"Error in reminder scheduler: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    def stop_reminder_scheduler(self):
        """Stop the reminder scheduler"""
        logger.info("Stopping goal reminder scheduler...")
        self.is_running = False
    
    async def process_due_reminders(self):
        """Process all due reminders and send notifications"""
        logger.info("Processing due goal reminders...")
        
        # Get database session
        db_gen = get_db()
        db: Session = next(db_gen)
        
        try:
            now = datetime.now(timezone.utc)
            
            # Find all active reminders that are due
            due_reminders = db.query(GoalReminder).join(Goal).filter(
                and_(
                    GoalReminder.is_active == True,
                    GoalReminder.next_reminder_at <= now,
                    Goal.status.in_([GoalStatus.NOT_STARTED, GoalStatus.IN_PROGRESS, GoalStatus.PAUSED])
                )
            ).all()
            
            logger.info(f"Found {len(due_reminders)} due reminders")
            
            for reminder in due_reminders:
                try:
                    await self.send_reminder_notifications(db, reminder)
                    
                    # Update reminder timestamps
                    reminder.last_sent_at = now
                    reminder.next_reminder_at = reminder.calculate_next_reminder()
                    
                    # If next reminder is None, deactivate the reminder
                    if reminder.next_reminder_at is None:
                        reminder.is_active = False
                        logger.warning(f"Deactivated reminder {reminder.id} - unable to calculate next reminder")
                    
                except Exception as e:
                    logger.error(f"Error processing reminder {reminder.id}: {e}")
                    continue
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error processing due reminders: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def send_reminder_notifications(self, db: Session, reminder: GoalReminder):
        """Send notifications for a specific reminder"""
        goal = db.query(Goal).filter(Goal.id == reminder.goal_id).first()
        if not goal:
            logger.error(f"Goal {reminder.goal_id} not found for reminder {reminder.id}")
            return
        
        # Determine notification recipients
        recipients = []
        
        if reminder.send_to_members:
            # Get all goal members
            recipients.extend(goal.members)
        else:
            # Just send to goal creator
            creator = db.query(User).filter(User.id == goal.created_by).first()
            if creator:
                recipients.append(creator)
        
        # Remove duplicates
        recipients = list(set(recipients))
        
        if not recipients:
            logger.warning(f"No recipients found for reminder {reminder.id}")
            return
        
        # Calculate goal progress for reminder context
        completion_percentage = goal.calculate_completion_percentage()
        probability = goal.get_probability_of_achievement()
        days_remaining = max(0, (goal.end_date - datetime.now(timezone.utc)).days)
        
        # Create notification message
        default_message = self.generate_default_reminder_message(goal, completion_percentage, probability, days_remaining)
        notification_message = reminder.reminder_message or default_message
        
        # Send notifications to each recipient
        for user in recipients:
            try:
                # Send in-app notification
                if reminder.send_in_app:
                    await self.send_in_app_notification(db, user, goal, notification_message)
                
                # Send email notification
                if reminder.send_email:
                    await self.send_email_notification(db, user, goal, notification_message)
                
            except Exception as e:
                logger.error(f"Error sending notification to user {user.id} for reminder {reminder.id}: {e}")
    
    async def send_in_app_notification(self, db: Session, user: User, goal: Goal, message: str):
        """Send in-app notification"""
        try:
            notification = Notification(
                user_id=user.id,
                title=f"Goal Reminder: {goal.title}",
                message=message,
                notification_type="goal_reminder",
                priority="normal",
                metadata={
                    "goal_id": goal.id,
                    "goal_title": goal.title,
                    "goal_type": goal.goal_type.value,
                    "goal_status": goal.status.value,
                    "completion_percentage": goal.calculate_completion_percentage(),
                    "probability_of_achievement": goal.get_probability_of_achievement(),
                    "days_remaining": max(0, (goal.end_date - datetime.now(timezone.utc)).days)
                }
            )
            db.add(notification)
            logger.info(f"Created in-app notification for user {user.id} and goal {goal.id}")
            
        except Exception as e:
            logger.error(f"Error creating in-app notification for user {user.id}: {e}")
    
    async def send_email_notification(self, db: Session, user: User, goal: Goal, message: str):
        """Send email notification (placeholder - implement with actual email service)"""
        try:
            # TODO: Implement actual email sending
            # For now, just log the email that would be sent
            logger.info(f"Would send email to {user.email} for goal '{goal.title}': {message}")
            
            # You would integrate with your email service here
            # Example: await email_service.send_goal_reminder(user.email, goal, message)
            
        except Exception as e:
            logger.error(f"Error sending email notification to {user.email}: {e}")
    
    def generate_default_reminder_message(self, goal: Goal, completion_percentage: float, probability: float, days_remaining: int) -> str:
        """Generate a default reminder message based on goal status"""
        
        # Create contextual message based on goal progress
        if completion_percentage >= 100:
            return f"🎉 Great job! Your goal '{goal.title}' is complete!"
        
        elif completion_percentage >= 75:
            return f"🚀 You're almost there! Your goal '{goal.title}' is {completion_percentage:.0f}% complete with {days_remaining} days remaining."
        
        elif completion_percentage >= 50:
            return f"💪 Keep going! Your goal '{goal.title}' is {completion_percentage:.0f}% complete. {days_remaining} days left to reach your target."
        
        elif completion_percentage >= 25:
            return f"⚡ Time to focus! Your goal '{goal.title}' is {completion_percentage:.0f}% complete. With {days_remaining} days remaining, now's the time to accelerate."
        
        elif days_remaining <= 7:
            return f"🚨 Urgent: Your goal '{goal.title}' has only {days_remaining} days left! Current progress: {completion_percentage:.0f}%"
        
        elif days_remaining <= 30:
            return f"⏰ Your goal '{goal.title}' is approaching its deadline in {days_remaining} days. Current progress: {completion_percentage:.0f}%"
        
        else:
            return f"📋 Reminder: Your goal '{goal.title}' needs attention. Current progress: {completion_percentage:.0f}% with {days_remaining} days remaining."
    
    async def update_overdue_goals(self):
        """Update status of overdue goals"""
        logger.info("Checking for overdue goals...")
        
        db_gen = get_db()
        db: Session = next(db_gen)
        
        try:
            now = datetime.now(timezone.utc)
            
            # Find goals that are overdue but not marked as such
            overdue_goals = db.query(Goal).filter(
                and_(
                    Goal.end_date < now,
                    Goal.status.in_([GoalStatus.NOT_STARTED, GoalStatus.IN_PROGRESS, GoalStatus.PAUSED]),
                    Goal.is_archived == False
                )
            ).all()
            
            logger.info(f"Found {len(overdue_goals)} overdue goals")
            
            for goal in overdue_goals:
                goal.status = GoalStatus.OVERDUE
                
                # Send overdue notification to goal members
                await self.send_overdue_notification(db, goal)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating overdue goals: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def send_overdue_notification(self, db: Session, goal: Goal):
        """Send overdue notification for a goal"""
        try:
            recipients = list(goal.members) if goal.members else []
            
            # Add creator if not in members
            creator = db.query(User).filter(User.id == goal.created_by).first()
            if creator and creator not in recipients:
                recipients.append(creator)
            
            overdue_message = f"⚠️ Your goal '{goal.title}' is now overdue. Consider updating the deadline or marking it as completed if finished."
            
            for user in recipients:
                notification = Notification(
                    user_id=user.id,
                    title=f"Goal Overdue: {goal.title}",
                    message=overdue_message,
                    notification_type="goal_overdue",
                    priority="high",
                    metadata={
                        "goal_id": goal.id,
                        "goal_title": goal.title,
                        "original_end_date": goal.end_date.isoformat(),
                        "completion_percentage": goal.calculate_completion_percentage()
                    }
                )
                db.add(notification)
            
            logger.info(f"Sent overdue notifications for goal {goal.id}")
            
        except Exception as e:
            logger.error(f"Error sending overdue notification for goal {goal.id}: {e}")

# Global instance
goal_reminder_service = GoalReminderService()

async def start_goal_reminder_scheduler():
    """Start the goal reminder scheduler"""
    await goal_reminder_service.start_reminder_scheduler()

def stop_goal_reminder_scheduler():
    """Stop the goal reminder scheduler"""
    goal_reminder_service.stop_reminder_scheduler()
