from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from datetime import datetime, timedelta
import uuid
import json

from ....db.database import get_db
from ....models.user import User
from ....models.task import Task, TaskStatus
from ....models.project import Project
from ....models.organization import Organization
from ...deps import get_current_active_user, require_manager, get_current_organization

router = APIRouter()


@router.get("/rules")
async def get_automation_rules(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get automation rules for the organization"""
    
    # TODO: Implement automation rules table
    # For now, return default rules
    default_rules = [
        {
            "id": "auto-1",
            "name": "Task Status Change Notification",
            "description": "Notify team members when task status changes",
            "trigger": "task_status_changed",
            "conditions": {
                "status_from": ["todo", "in_progress"],
                "status_to": ["completed", "blocked"]
            },
            "actions": [
                {
                    "type": "notification",
                    "target": "team_members",
                    "message": "Task {task_title} status changed from {old_status} to {new_status}"
                }
            ],
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()
        },
        {
            "id": "auto-2", 
            "name": "Deadline Reminder",
            "description": "Send reminders for tasks approaching deadline",
            "trigger": "task_due_soon",
            "conditions": {
                "days_before_deadline": 1,
                "status": ["todo", "in_progress"]
            },
            "actions": [
                {
                    "type": "notification",
                    "target": "assignee",
                    "message": "Task {task_title} is due tomorrow!"
                }
            ],
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()
        },
        {
            "id": "auto-3",
            "name": "Project Completion Celebration",
            "description": "Celebrate when projects are completed",
            "trigger": "project_completed",
            "conditions": {},
            "actions": [
                {
                    "type": "notification",
                    "target": "project_team",
                    "message": "🎉 Project {project_name} has been completed! Great work team!"
                }
            ],
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()
        }
    ]
    
    return {"rules": default_rules}


@router.post("/rules")
async def create_automation_rule(
    rule_data: dict,
    current_user: User = Depends(require_manager),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new automation rule"""
    
    # Validate rule structure
    required_fields = ["name", "trigger", "actions"]
    for field in required_fields:
        if field not in rule_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: {field}"
            )
    
    # TODO: Save rule to database
    new_rule = {
        "id": str(uuid.uuid4()),
        "name": rule_data["name"],
        "description": rule_data.get("description", ""),
        "trigger": rule_data["trigger"],
        "conditions": rule_data.get("conditions", {}),
        "actions": rule_data["actions"],
        "is_active": rule_data.get("is_active", True),
        "created_by": current_user.id,
        "organization_id": current_org.id,
        "created_at": datetime.utcnow().isoformat()
    }
    
    return {
        "message": "Automation rule created successfully",
        "rule": new_rule
    }


@router.get("/templates")
async def get_automation_templates(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get pre-built automation templates"""
    
    templates = [
        {
            "id": "template-1",
            "name": "Client Communication",
            "description": "Automatically notify clients about project updates",
            "category": "client_management",
            "rules": [
                {
                    "trigger": "project_milestone_reached",
                    "actions": [
                        {
                            "type": "email",
                            "target": "client",
                            "template": "milestone_notification"
                        }
                    ]
                }
            ]
        },
        {
            "id": "template-2",
            "name": "Team Productivity",
            "description": "Track and improve team performance",
            "category": "team_management",
            "rules": [
                {
                    "trigger": "task_completed",
                    "actions": [
                        {
                            "type": "notification",
                            "target": "team_lead",
                            "message": "Task completed by {assignee_name}"
                        }
                    ]
                }
            ]
        },
        {
            "id": "template-3",
            "name": "Quality Assurance",
            "description": "Ensure code quality and review processes",
            "category": "development",
            "rules": [
                {
                    "trigger": "task_status_changed",
                    "conditions": {
                        "status_to": "in_review"
                    },
                    "actions": [
                        {
                            "type": "notification",
                            "target": "reviewers",
                            "message": "New task ready for review: {task_title}"
                        }
                    ]
                }
            ]
        }
    ]
    
    return {"templates": templates}


@router.post("/smart-assignment")
async def get_smart_assignment_suggestions(
    task_data: dict,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get smart task assignment suggestions"""
    
    # Get team members with their current workload
    team_query = select(
        User.id,
        User.first_name,
        User.last_name,
        User.email,
        func.count(Task.id).label("active_tasks"),
        func.coalesce(func.sum(Task.estimated_hours), 0).label("estimated_hours")
    ).select_from(
        User.outerjoin(Task, and_(
            Task.assignee_id == User.id,
            Task.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS])
        ))
    ).where(
        User.organization_id == current_org.id,
        User.is_active == True
    ).group_by(User.id, User.first_name, User.last_name, User.email)
    
    team_result = await db.execute(team_query)
    team_members = team_result.fetchall()
    
    # Calculate workload scores
    suggestions = []
    for member in team_members:
        workload_score = (member.active_tasks * 10) + (member.estimated_hours * 0.5)
        
        # Consider skills and availability (simplified)
        availability_score = 100 - min(workload_score, 100)
        
        suggestions.append({
            "user_id": member.id,
            "name": f"{member.first_name} {member.last_name}",
            "email": member.email,
            "current_tasks": member.active_tasks,
            "estimated_hours": float(member.estimated_hours or 0),
            "workload_score": workload_score,
            "availability_score": availability_score,
            "recommendation": "High" if availability_score > 70 else "Medium" if availability_score > 40 else "Low"
        })
    
    # Sort by availability score
    suggestions.sort(key=lambda x: x["availability_score"], reverse=True)
    
    return {
        "task": task_data,
        "suggestions": suggestions[:5],  # Top 5 suggestions
        "best_match": suggestions[0] if suggestions else None
    }


@router.post("/deadline-reminders")
async def setup_deadline_reminders(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Setup automatic deadline reminders"""
    
    # Get tasks due soon
    tomorrow = datetime.now() + timedelta(days=1)
    next_week = datetime.now() + timedelta(days=7)
    
    due_soon_query = select(Task).join(Project).where(
        and_(
            Project.organization_id == current_org.id,
            Task.due_date >= tomorrow,
            Task.due_date <= next_week,
            Task.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS]),
            Task.assignee_id.is_not(None)
        )
    )
    
    due_soon_result = await db.execute(due_soon_query)
    due_soon_tasks = due_soon_result.scalars().all()
    
    # Setup reminders for each task
    reminders_created = 0
    for task in due_soon_tasks:
        days_until_due = (task.due_date - datetime.now()).days
        
        if days_until_due == 1:
            # Due tomorrow - high priority
            background_tasks.add_task(
                send_deadline_reminder,
                task.id,
                "high",
                f"🚨 Task '{task.title}' is due TOMORROW!"
            )
        elif days_until_due <= 3:
            # Due this week - medium priority
            background_tasks.add_task(
                send_deadline_reminder,
                task.id,
                "medium",
                f"⚠️ Task '{task.title}' is due in {days_until_due} days"
            )
        else:
            # Due next week - low priority
            background_tasks.add_task(
                send_deadline_reminder,
                task.id,
                "low",
                f"📅 Task '{task.title}' is due in {days_until_due} days"
            )
        
        reminders_created += 1
    
    return {
        "message": f"Deadline reminders setup for {reminders_created} tasks",
        "reminders_created": reminders_created
    }


@router.post("/workflow-automation")
async def trigger_workflow_automation(
    trigger_data: dict,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Trigger workflow automation based on events"""
    
    trigger_type = trigger_data.get("type")
    entity_id = trigger_data.get("entity_id")
    old_data = trigger_data.get("old_data", {})
    new_data = trigger_data.get("new_data", {})
    
    if trigger_type == "task_status_changed":
        # Handle task status change
        await handle_task_status_change(entity_id, old_data, new_data, current_org, db)
    elif trigger_type == "project_milestone_reached":
        # Handle project milestone
        await handle_project_milestone(entity_id, new_data, current_org, db)
    elif trigger_type == "deadline_approaching":
        # Handle deadline reminder
        await handle_deadline_reminder(entity_id, new_data, current_org, db)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown trigger type: {trigger_type}"
        )
    
    return {"message": f"Workflow automation triggered for {trigger_type}"}


# Helper functions for automation
async def send_deadline_reminder(task_id: str, priority: str, message: str):
    """Send deadline reminder (placeholder)"""
    # TODO: Implement actual notification sending
    print(f"Sending {priority} priority reminder: {message} for task {task_id}")


async def handle_task_status_change(task_id: str, old_data: dict, new_data: dict, org: Organization, db: AsyncSession):
    """Handle task status change automation"""
    old_status = old_data.get("status")
    new_status = new_data.get("status")
    
    # Notify team members about status change
    if old_status != new_status:
        # TODO: Send notifications to relevant team members
        print(f"Task {task_id} status changed from {old_status} to {new_status}")
        
        # Auto-assign next person in workflow if applicable
        if new_status == TaskStatus.IN_REVIEW:
            # TODO: Auto-assign to reviewers
            pass
        elif new_status == TaskStatus.COMPLETED:
            # TODO: Notify project manager
            pass


async def handle_project_milestone(project_id: str, milestone_data: dict, org: Organization, db: AsyncSession):
    """Handle project milestone automation"""
    # TODO: Implement milestone celebration and notifications
    print(f"Project {project_id} reached milestone: {milestone_data}")


async def handle_deadline_reminder(task_id: str, task_data: dict, org: Organization, db: AsyncSession):
    """Handle deadline reminder automation"""
    # TODO: Implement deadline reminder logic
    print(f"Setting up deadline reminder for task {task_id}")
