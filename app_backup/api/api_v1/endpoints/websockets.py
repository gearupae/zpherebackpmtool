from typing import Dict, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import uuid
from datetime import datetime

from ....db.database import get_db
from ....models.user import User
from ....models.project import Project
from ....models.task import Task
from ....models.organization import Organization
from ....core.security import verify_token

router = APIRouter()

# Connection manager for WebSocket connections
class ConnectionManager:
    def __init__(self):
        # Store connections by organization_id and user_id
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        # Store project-specific connections
        self.project_connections: Dict[str, Dict[str, WebSocket]] = {}
        # Store task-specific connections
        self.task_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str, organization_id: str):
        """Connect a user to their organization channel"""
        await websocket.accept()
        
        if organization_id not in self.active_connections:
            self.active_connections[organization_id] = {}
        
        self.active_connections[organization_id][user_id] = websocket

    async def connect_to_project(self, websocket: WebSocket, user_id: str, project_id: str):
        """Connect a user to a specific project channel"""
        await websocket.accept()
        
        if project_id not in self.project_connections:
            self.project_connections[project_id] = {}
        
        self.project_connections[project_id][user_id] = websocket

    async def connect_to_task(self, websocket: WebSocket, user_id: str, task_id: str):
        """Connect a user to a specific task channel"""
        await websocket.accept()
        
        if task_id not in self.task_connections:
            self.task_connections[task_id] = {}
        
        self.task_connections[task_id][user_id] = websocket

    def disconnect(self, user_id: str, organization_id: str = None, project_id: str = None, task_id: str = None):
        """Disconnect a user from channels"""
        if organization_id and organization_id in self.active_connections:
            self.active_connections[organization_id].pop(user_id, None)
            if not self.active_connections[organization_id]:
                del self.active_connections[organization_id]
        
        if project_id and project_id in self.project_connections:
            self.project_connections[project_id].pop(user_id, None)
            if not self.project_connections[project_id]:
                del self.project_connections[project_id]
        
        if task_id and task_id in self.task_connections:
            self.task_connections[task_id].pop(user_id, None)
            if not self.task_connections[task_id]:
                del self.task_connections[task_id]

    async def send_to_organization(self, message: dict, organization_id: str, exclude_user: str = None):
        """Send message to all users in an organization"""
        if organization_id in self.active_connections:
            for user_id, connection in self.active_connections[organization_id].items():
                if exclude_user and user_id == exclude_user:
                    continue
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    # Remove dead connections
                    self.active_connections[organization_id].pop(user_id, None)

    async def send_to_project(self, message: dict, project_id: str, exclude_user: str = None):
        """Send message to all users watching a project"""
        if project_id in self.project_connections:
            for user_id, connection in self.project_connections[project_id].items():
                if exclude_user and user_id == exclude_user:
                    continue
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    # Remove dead connections
                    self.project_connections[project_id].pop(user_id, None)

    async def send_to_task(self, message: dict, task_id: str, exclude_user: str = None):
        """Send message to all users watching a task"""
        if task_id in self.task_connections:
            for user_id, connection in self.task_connections[task_id].items():
                if exclude_user and user_id == exclude_user:
                    continue
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    # Remove dead connections
                    self.task_connections[task_id].pop(user_id, None)

    async def send_to_user(self, message: dict, user_id: str, organization_id: str):
        """Send message to a specific user"""
        if organization_id in self.active_connections and user_id in self.active_connections[organization_id]:
            try:
                await self.active_connections[organization_id][user_id].send_text(json.dumps(message))
            except:
                # Remove dead connection
                self.active_connections[organization_id].pop(user_id, None)

# Global connection manager instance
manager = ConnectionManager()


async def get_current_user_ws(token: str, db: AsyncSession) -> User:
    """Get current user from WebSocket token"""
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    return user


@router.websocket("/ws/organization")
async def websocket_organization(websocket: WebSocket, token: str, db: AsyncSession = Depends(get_db)):
    """WebSocket endpoint for organization-wide updates"""
    try:
        # Authenticate user
        user = await get_current_user_ws(token, db)
        
        # Connect to organization channel
        await manager.connect(websocket, user.id, user.organization_id)
        
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "Connected to organization updates",
            "user_id": user.id,
            "organization_id": user.organization_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        while True:
            # Listen for client messages
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle different message types
            if message_data.get("type") == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            elif message_data.get("type") == "broadcast":
                # Broadcast message to all organization members
                broadcast_message = {
                    "type": "broadcast",
                    "from_user": f"{user.first_name} {user.last_name}",
                    "message": message_data.get("message", ""),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await manager.send_to_organization(broadcast_message, user.organization_id, exclude_user=user.id)
                
    except WebSocketDisconnect:
        manager.disconnect(user.id, organization_id=user.organization_id)
    except Exception as e:
        await websocket.close(code=1000)


@router.websocket("/ws/projects/{project_id}")
async def websocket_project(websocket: WebSocket, project_id: str, token: str, db: AsyncSession = Depends(get_db)):
    """WebSocket endpoint for project-specific updates"""
    try:
        # Authenticate user
        user = await get_current_user_ws(token, db)
        
        # Verify user has access to project
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == user.organization_id
            )
        )
        project = result.scalar_one_or_none()
        
        if not project:
            await websocket.close(code=4004, reason="Project not found")
            return
        
        # Connect to project channel
        await manager.connect_to_project(websocket, user.id, project_id)
        
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": f"Connected to project: {project.name}",
            "project_id": project_id,
            "user_id": user.id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        while True:
            # Listen for client messages
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle different message types
            if message_data.get("type") == "project_update":
                # Broadcast project update to all project watchers
                update_message = {
                    "type": "project_update",
                    "project_id": project_id,
                    "updated_by": f"{user.first_name} {user.last_name}",
                    "changes": message_data.get("changes", {}),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await manager.send_to_project(update_message, project_id, exclude_user=user.id)
                
    except WebSocketDisconnect:
        manager.disconnect(user.id, project_id=project_id)
    except Exception as e:
        await websocket.close(code=1000)


@router.websocket("/ws/tasks/{task_id}")
async def websocket_task(websocket: WebSocket, task_id: str, token: str, db: AsyncSession = Depends(get_db)):
    """WebSocket endpoint for task-specific updates"""
    try:
        # Authenticate user
        user = await get_current_user_ws(token, db)
        
        # Verify user has access to task
        result = await db.execute(
            select(Task).join(Project).where(
                Task.id == task_id,
                Project.organization_id == user.organization_id
            )
        )
        task = result.scalar_one_or_none()
        
        if not task:
            await websocket.close(code=4004, reason="Task not found")
            return
        
        # Connect to task channel
        await manager.connect_to_task(websocket, user.id, task_id)
        
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": f"Connected to task: {task.title}",
            "task_id": task_id,
            "user_id": user.id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        while True:
            # Listen for client messages
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle different message types
            if message_data.get("type") == "task_update":
                # Broadcast task update to all task watchers
                update_message = {
                    "type": "task_update",
                    "task_id": task_id,
                    "updated_by": f"{user.first_name} {user.last_name}",
                    "changes": message_data.get("changes", {}),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await manager.send_to_task(update_message, task_id, exclude_user=user.id)
                
            elif message_data.get("type") == "task_comment":
                # Broadcast new comment to all task watchers
                comment_message = {
                    "type": "task_comment",
                    "task_id": task_id,
                    "comment_id": str(uuid.uuid4()),
                    "author": f"{user.first_name} {user.last_name}",
                    "author_id": user.id,
                    "content": message_data.get("content", ""),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await manager.send_to_task(comment_message, task_id)
                
    except WebSocketDisconnect:
        manager.disconnect(user.id, task_id=task_id)
    except Exception as e:
        await websocket.close(code=1000)


@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket, token: str, db: AsyncSession = Depends(get_db)):
    """WebSocket endpoint for real-time notifications"""
    try:
        # Authenticate user
        user = await get_current_user_ws(token, db)
        
        # Connect to organization channel for notifications
        await manager.connect(websocket, user.id, user.organization_id)
        
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "Connected to notifications",
            "user_id": user.id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        while True:
            # Keep connection alive and listen for ping
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }))
                
    except WebSocketDisconnect:
        manager.disconnect(user.id, organization_id=user.organization_id)
    except Exception as e:
        await websocket.close(code=1000)


# Helper functions for sending real-time updates from other parts of the application

async def send_task_update(task_id: str, updated_by: str, changes: dict):
    """Send task update notification"""
    message = {
        "type": "task_update",
        "task_id": task_id,
        "updated_by": updated_by,
        "changes": changes,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.send_to_task(message, task_id)


async def send_project_update(project_id: str, updated_by: str, changes: dict):
    """Send project update notification"""
    message = {
        "type": "project_update", 
        "project_id": project_id,
        "updated_by": updated_by,
        "changes": changes,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.send_to_project(message, project_id)


async def send_notification(user_id: str, organization_id: str, notification: dict):
    """Send notification to a specific user"""
    message = {
        "type": "notification",
        "notification": notification,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.send_to_user(message, user_id, organization_id)
