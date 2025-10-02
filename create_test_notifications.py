#!/usr/bin/env python3
"""
Script to create test notifications in the database
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text, select
from app.models.user import User
from app.models.organization import Organization
from app.models.notification import Notification, NotificationType, NotificationPriority

def create_test_notifications():
    """Create some test notifications for demo purposes"""
    
    # Connect directly to PostgreSQL
    database_url = "postgresql+psycopg2://zphere_user:zphere_password@localhost:5432/zphere_db"
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        # Get the first user from the database
        user_result = conn.execute(text("SELECT id, email, organization_id FROM users LIMIT 1"))
        user_row = user_result.fetchone()
        
        if not user_row:
            print("No users found in database. Please create a user first.")
            return
        
        user_id, user_email, org_id = user_row
        print(f"Creating test notifications for user: {user_email}")
        
        # Create various types of test notifications using direct SQL
        import json
        
        test_notifications = [
            {
                "title": "Welcome to Zphere!",
                "message": "Welcome to your new project management system. Get started by creating your first project.",
                "notification_type": "SYSTEM_ALERT",
                "priority": "NORMAL",
                "context_data": {"onboarding": True},
                "source": "system",
            },
            {
                "title": "New Task Assigned",
                "message": "You have been assigned to task 'Complete project documentation'",
                "notification_type": "TASK_ASSIGNED",
                "priority": "HIGH",
                "context_data": {"task_id": "sample-task-123", "project_id": "sample-project-456"},
                "source": "task_system",
            },
            {
                "title": "Task Due Soon",
                "message": "Task 'Review mockups' is due tomorrow",
                "notification_type": "TASK_DUE_SOON",
                "priority": "URGENT",
                "context_data": {"task_id": "sample-task-456", "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat()},
                "source": "reminder_system",
            },
            {
                "title": "Project Status Updated",
                "message": "Project 'Website Redesign' status changed to In Progress",
                "notification_type": "PROJECT_STATUS_CHANGED",
                "priority": "NORMAL",
                "context_data": {"project_id": "sample-project-789", "new_status": "in_progress"},
                "source": "project_system",
            },
            {
                "title": "New Comment",
                "message": "John Doe commented on task 'Update user interface'",
                "notification_type": "TASK_COMMENT",
                "priority": "NORMAL",
                "context_data": {"task_id": "sample-task-789", "commenter": "John Doe"},
                "source": "comment_system",
            },
            {
                "title": "You've been mentioned",
                "message": f"Sarah mentioned you in a comment: @{user_email} can you review this?",
                "notification_type": "MENTION",
                "priority": "HIGH",
                "context_data": {"mentioned_by": "Sarah", "context": "task_comment", "task_id": "sample-task-999"},
                "source": "mention_system",
            },
        ]
        
        created_count = 0
        for notif_data in test_notifications:
            notification_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            conn.execute(text("""
                INSERT INTO notifications (
                    id, user_id, organization_id, title, message, notification_type, priority,
                    context_data, source, is_read, auto_generated, relevance_score,
                    delivery_channels, tags, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :organization_id, :title, :message, :notification_type, :priority,
                    :context_data, :source, :is_read, :auto_generated, :relevance_score,
                    :delivery_channels, :tags, :created_at, :updated_at
                )
            """), {
                "id": notification_id,
                "user_id": user_id,
                "organization_id": org_id,
                "title": notif_data["title"],
                "message": notif_data["message"],
                "notification_type": notif_data["notification_type"],
                "priority": notif_data["priority"],
                "context_data": json.dumps(notif_data["context_data"]),
                "source": notif_data["source"],
                "is_read": False,
                "auto_generated": True,
                "relevance_score": 0.8,
                "delivery_channels": json.dumps(["in_app"]),
                "tags": json.dumps([]),
                "created_at": now,
                "updated_at": now,
            })
            created_count += 1
            
        # Create one older read notification
        old_notification_id = str(uuid.uuid4())
        read_time = datetime.utcnow() - timedelta(hours=2)
        
        conn.execute(text("""
            INSERT INTO notifications (
                id, user_id, organization_id, title, message, notification_type, priority,
                context_data, source, is_read, read_at, auto_generated, relevance_score,
                delivery_channels, tags, created_at, updated_at
            ) VALUES (
                :id, :user_id, :organization_id, :title, :message, :notification_type, :priority,
                :context_data, :source, :is_read, :read_at, :auto_generated, :relevance_score,
                :delivery_channels, :tags, :created_at, :updated_at
            )
        """), {
            "id": old_notification_id,
            "user_id": user_id,
            "organization_id": org_id,
            "title": "System Maintenance Completed",
            "message": "Scheduled system maintenance has been completed successfully.",
            "notification_type": "SYSTEM_ALERT",
            "priority": "LOW",
            "context_data": json.dumps({"maintenance_type": "database_optimization"}),
            "source": "maintenance_system",
            "is_read": True,
            "read_at": read_time,
            "auto_generated": True,
            "relevance_score": 0.3,
            "delivery_channels": json.dumps(["in_app"]),
            "tags": json.dumps(["maintenance"]),
            "created_at": read_time,
            "updated_at": read_time,
        })
        created_count += 1
        
        conn.commit()
        
        print(f"✅ Successfully created {created_count} test notifications!")
        print(f"   User: {user_email} ({user_id})")
        print(f"   Organization: {org_id}")
        print("\nYou can now test the notifications API at:")
        print("   GET /api/v1/notifications")
        print("   GET /api/v1/notifications?unread_only=true")
        
def main():
    print("Creating test notifications...")
    try:
        create_test_notifications()
    except Exception as e:
        print(f"❌ Error creating test notifications: {str(e)}")

if __name__ == "__main__":
    main()
