from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from ....models.user import User
from ....models.task import Task as TaskModel, TaskStatus, TaskPriority, TaskType, TaskComment, TaskAttachment
from ....models.task_document import TaskDocument, DocumentType
from ....models.project import Project
from ....schemas.task import Task, TaskCreate, TaskUpdate
from ...deps_tenant import get_current_active_user_master
from ....api.deps_tenant import get_master_db as get_db
from ...deps_tenant import get_tenant_db
from ....db.tenant_manager import tenant_manager
from sqlalchemy import select as sa_select
import uuid
from datetime import datetime
from .websockets import send_notification as ws_send_notification
import os
import aiofiles
from pathlib import Path
from pydantic import BaseModel
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/", response_model=List[Task])
async def get_tasks(
    current_user: User = Depends(get_current_active_user_master),
    project_id: str = None,
    status: TaskStatus = None,
    priority: TaskPriority = None,
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get all tasks for current user with optional filters"""
    
    # Build query based on filters
    query = select(TaskModel).join(Project).where(
        Project.organization_id == current_user.organization_id
    )
    
    if project_id:
        query = query.where(TaskModel.project_id == project_id)
    
    if status:
        query = query.where(TaskModel.status == status)
    
    if priority:
        query = query.where(TaskModel.priority == priority)
    
    # Order by priority and due date
    query = query.order_by(TaskModel.priority.desc(), TaskModel.due_date.asc())
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    return tasks


@router.post("/", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new task or subtask (when parent_task_id is provided)"""
    
    # Determine target project and validate access
    target_project_id = None
    parent_task = None
    if task_data.parent_task_id:
        # Verify parent task access and derive project from parent
        parent_task = await verify_task_access(task_data.parent_task_id, current_user, db)
        target_project_id = parent_task.project_id
    else:
        # Verify project exists and user has access
        project_query = select(Project).where(
            (Project.id == task_data.project_id) &
            (Project.organization_id == current_user.organization_id)
        )
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        target_project_id = project.id
    
    # Ensure referenced users exist in tenant DB (creator and assignee)
    try:
        # Ensure current user (creator) exists in tenant DB (usually ensured by deps)
        creator_res = await db.execute(sa_select(User).where(User.id == current_user.id))
        if not creator_res.scalar_one_or_none():
            master_session = await tenant_manager.get_master_session()
            try:
                mu_res = await master_session.execute(sa_select(User).where(User.id == current_user.id))
                mu = mu_res.scalar_one_or_none()
                if mu:
                    db.add(User(
                        id=mu.id,
                        email=mu.email,
                        username=mu.username,
                        first_name=mu.first_name,
                        last_name=mu.last_name,
                        hashed_password=mu.hashed_password,
                        organization_id=mu.organization_id,
                        role=mu.role,
                        status=mu.status,
                        is_active=mu.is_active,
                        is_verified=mu.is_verified,
                        timezone=mu.timezone,
                        phone=mu.phone,
                        bio=mu.bio,
                        preferences=mu.preferences,
                        notification_settings=mu.notification_settings,
                        last_login=mu.last_login,
                        password_changed_at=mu.password_changed_at,
                        avatar_url=getattr(mu, "avatar_url", None),
                    ))
                    await db.flush()
            finally:
                await master_session.close()
        # Ensure assignee exists if provided
        if task_data.assignee_id:
            a_res = await db.execute(sa_select(User).where(User.id == task_data.assignee_id))
            if not a_res.scalar_one_or_none():
                master_session = await tenant_manager.get_master_session()
                try:
                    mu_res = await master_session.execute(sa_select(User).where(User.id == task_data.assignee_id))
                    mu = mu_res.scalar_one_or_none()
                    if mu:
                        db.add(User(
                            id=mu.id,
                            email=mu.email,
                            username=mu.username,
                            first_name=mu.first_name,
                            last_name=mu.last_name,
                            hashed_password=mu.hashed_password,
                            organization_id=mu.organization_id,
                            role=mu.role,
                            status=mu.status,
                            is_active=mu.is_active,
                            is_verified=mu.is_verified,
                            timezone=mu.timezone,
                            phone=mu.phone,
                            bio=mu.bio,
                            preferences=mu.preferences,
                            notification_settings=mu.notification_settings,
                            last_login=mu.last_login,
                            password_changed_at=mu.password_changed_at,
                            avatar_url=getattr(mu, "avatar_url", None),
                        ))
                        await db.flush()
                finally:
                    await master_session.close()
    except Exception:
        # Best-effort; proceed
        pass

    # Prepare payload with derived project and type
    payload = task_data.model_dump()
    payload["project_id"] = target_project_id
    if parent_task is not None:
        payload["task_type"] = TaskType.SUBTASK

    # Create task
    task = TaskModel(
        id=str(uuid.uuid4()),
        created_by_id=current_user.id,
        **payload
    )
    
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Real-time notification to creator and assignee (if any)
    try:
        is_subtask = parent_task is not None
        ws_payload = {
            "id": str(uuid.uuid4()),
            "title": f"{'Subtask' if is_subtask else 'Task'} created: {task.title}",
            "message": f"A new {'subtask' if is_subtask else 'task'} was created.",
            "notification_type": "system_alert",
            "created_at": datetime.utcnow().isoformat(),
            "context": {"task_id": task.id, "project_id": task.project_id, "event": "subtask_created" if is_subtask else "task_created"},
        }
        await ws_send_notification(current_user.id, current_user.organization_id, ws_payload)
        if task.assignee_id and task.assignee_id != current_user.id:
            await ws_send_notification(task.assignee_id, current_user.organization_id, ws_payload)
    except Exception:
        pass
    
    return task


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific task"""
    
    query = select(TaskModel).join(Project).where(
        (TaskModel.id == task_id) &
        (Project.organization_id == current_user.organization_id)
    )
    
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return task


@router.put("/{task_id}", response_model=Task)
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a task"""
    
    query = select(TaskModel).join(Project).where(
        (TaskModel.id == task_id) &
        (Project.organization_id == current_user.organization_id)
    )
    
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
# Update task fields
    update_data = task_data.model_dump(exclude_unset=True)

    # Ensure referenced users exist in tenant DB if present in update
    try:
        # created_by_id
        if update_data.get("created_by_id"):
            uid = update_data["created_by_id"]
            u_res = await db.execute(sa_select(User).where(User.id == uid))
            if not u_res.scalar_one_or_none():
                master_session = await tenant_manager.get_master_session()
                try:
                    mu_res = await master_session.execute(sa_select(User).where(User.id == uid))
                    mu = mu_res.scalar_one_or_none()
                    if mu:
                        db.add(User(
                            id=mu.id,
                            email=mu.email,
                            username=mu.username,
                            first_name=mu.first_name,
                            last_name=mu.last_name,
                            hashed_password=mu.hashed_password,
                            organization_id=mu.organization_id,
                            role=mu.role,
                            status=mu.status,
                            is_active=mu.is_active,
                            is_verified=mu.is_verified,
                            timezone=mu.timezone,
                            phone=mu.phone,
                            bio=mu.bio,
                            preferences=mu.preferences,
                            notification_settings=mu.notification_settings,
                            last_login=mu.last_login,
                            password_changed_at=mu.password_changed_at,
                            avatar_url=getattr(mu, "avatar_url", None),
                        ))
                        await db.flush()
                finally:
                    await master_session.close()
        # assignee_id
        if update_data.get("assignee_id"):
            uid = update_data["assignee_id"]
            u_res = await db.execute(sa_select(User).where(User.id == uid))
            if not u_res.scalar_one_or_none():
                master_session = await tenant_manager.get_master_session()
                try:
                    mu_res = await master_session.execute(sa_select(User).where(User.id == uid))
                    mu = mu_res.scalar_one_or_none()
                    if mu:
                        db.add(User(
                            id=mu.id,
                            email=mu.email,
                            username=mu.username,
                            first_name=mu.first_name,
                            last_name=mu.last_name,
                            hashed_password=mu.hashed_password,
                            organization_id=mu.organization_id,
                            role=mu.role,
                            status=mu.status,
                            is_active=mu.is_active,
                            is_verified=mu.is_verified,
                            timezone=mu.timezone,
                            phone=mu.phone,
                            bio=mu.bio,
                            preferences=mu.preferences,
                            notification_settings=mu.notification_settings,
                            last_login=mu.last_login,
                            password_changed_at=mu.password_changed_at,
                            avatar_url=getattr(mu, "avatar_url", None),
                        ))
                        await db.flush()
                finally:
                    await master_session.close()
    except Exception:
        # Best-effort; continue
        pass

    for field, value in update_data.items():
        setattr(task, field, value)
    
    await db.commit()
    await db.refresh(task)

    # Real-time notification on update to creator and assignee
    try:
        ws_payload = {
            "id": str(uuid.uuid4()),
            "title": f"Task updated: {task.title}",
            "message": f"Fields updated: {', '.join(update_data.keys())}",
            "notification_type": "system_alert",
            "created_at": datetime.utcnow().isoformat(),
            "context": {"task_id": task.id, "project_id": task.project_id, "event": "task_updated", "fields": list(update_data.keys())},
        }
        await ws_send_notification(task.created_by_id, current_user.organization_id, ws_payload)
        if task.assignee_id:
            await ws_send_notification(task.assignee_id, current_user.organization_id, ws_payload)
    except Exception:
        pass
    
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Archive a task (soft delete)"""
    
    query = select(TaskModel).join(Project).where(
        (TaskModel.id == task_id) &
        (Project.organization_id == current_user.organization_id)
    )
    
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Soft delete by archiving
    task.is_archived = True
    await db.commit()


@router.get("/my-tasks", response_model=List[Task])
async def get_my_tasks(
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get tasks assigned to current user"""
    
    query = select(TaskModel).join(Project).where(
        (TaskModel.assignee_id == current_user.id) &
        (Project.organization_id == current_user.organization_id) &
        (TaskModel.is_archived == False)
    ).order_by(TaskModel.priority.desc(), TaskModel.due_date.asc())
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    return tasks


# Pydantic models for new features
class TaskCommentCreate(BaseModel):
    content: str
    parent_comment_id: str = None
    mentions: List[str] = []
    linked_tasks: List[str] = []

class TaskCommentUpdate(BaseModel):
    content: str
    mentions: List[str] = []
    linked_tasks: List[str] = []

class TaskDocumentCreate(BaseModel):
    title: str
    content: str
    document_type: DocumentType = DocumentType.NOTES
    is_template: bool = False
    tags: List[str] = []
    metadata: dict = {}

class TaskDocumentUpdate(BaseModel):
    title: str = None
    content: str = None
    document_type: DocumentType = None
    is_template: bool = None
    tags: List[str] = None
    metadata: dict = None


class SubtaskCreate(BaseModel):
    title: str
    description: str | None = None
    assignee_id: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    start_date: datetime | None = None
    due_date: datetime | None = None
    labels: List[str] = []
    tags: List[str] = []
    visible_to_customer: bool | None = False

class ActivityItem(BaseModel):
    id: str
    type: str
    title: str
    description: str
    user_name: str
    user_avatar: str = None
    created_at: str


# Helper function to verify task access
async def verify_task_access(task_id: str, current_user: User, db: AsyncSession) -> TaskModel:
    """Verify user has access to task and return task if found"""
    query = select(TaskModel).join(Project).where(
        (TaskModel.id == task_id) &
        (Project.organization_id == current_user.organization_id)
    )
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return task


# SUBTASKS ENDPOINTS

@router.get("/{task_id}/subtasks", response_model=List[Task])
async def list_subtasks(
    task_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """List subtasks for a given task"""
    # Verify parent task access
    await verify_task_access(task_id, current_user, db)

    query = select(TaskModel).where(
        TaskModel.parent_task_id == task_id
    ).order_by(TaskModel.priority.desc(), TaskModel.due_date.asc(), TaskModel.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/{task_id}/subtasks", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_subtask(
    task_id: str,
    subtask_data: SubtaskCreate,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a subtask under the given task"""
    # Verify parent task access and get parent
    parent = await verify_task_access(task_id, current_user, db)

    # Ensure referenced users exist in tenant DB (creator and assignee)
    try:
        # Ensure current user exists
        creator_res = await db.execute(sa_select(User).where(User.id == current_user.id))
        if not creator_res.scalar_one_or_none():
            master_session = await tenant_manager.get_master_session()
            try:
                mu_res = await master_session.execute(sa_select(User).where(User.id == current_user.id))
                mu = mu_res.scalar_one_or_none()
                if mu:
                    db.add(User(
                        id=mu.id,
                        email=mu.email,
                        username=mu.username,
                        first_name=mu.first_name,
                        last_name=mu.last_name,
                        hashed_password=mu.hashed_password,
                        organization_id=mu.organization_id,
                        role=mu.role,
                        status=mu.status,
                        is_active=mu.is_active,
                        is_verified=mu.is_verified,
                        timezone=mu.timezone,
                        phone=mu.phone,
                        bio=mu.bio,
                        preferences=mu.preferences,
                        notification_settings=mu.notification_settings,
                        last_login=mu.last_login,
                        password_changed_at=mu.password_changed_at,
                        avatar_url=getattr(mu, "avatar_url", None),
                    ))
                    await db.flush()
            finally:
                await master_session.close()
        # Ensure assignee exists if provided
        if subtask_data.assignee_id:
            a_res = await db.execute(sa_select(User).where(User.id == subtask_data.assignee_id))
            if not a_res.scalar_one_or_none():
                master_session = await tenant_manager.get_master_session()
                try:
                    mu_res = await master_session.execute(sa_select(User).where(User.id == subtask_data.assignee_id))
                    mu = mu_res.scalar_one_or_none()
                    if mu:
                        db.add(User(
                            id=mu.id,
                            email=mu.email,
                            username=mu.username,
                            first_name=mu.first_name,
                            last_name=mu.last_name,
                            hashed_password=mu.hashed_password,
                            organization_id=mu.organization_id,
                            role=mu.role,
                            status=mu.status,
                            is_active=mu.is_active,
                            is_verified=mu.is_verified,
                            timezone=mu.timezone,
                            phone=mu.phone,
                            bio=mu.bio,
                            preferences=mu.preferences,
                            notification_settings=mu.notification_settings,
                            last_login=mu.last_login,
                            password_changed_at=mu.password_changed_at,
                            avatar_url=getattr(mu, "avatar_url", None),
                        ))
                        await db.flush()
                finally:
                    await master_session.close()
    except Exception:
        # Best-effort; proceed
        pass

    # Create subtask
    subtask = TaskModel(
        id=str(uuid.uuid4()),
        created_by_id=current_user.id,
        project_id=parent.project_id,
        parent_task_id=task_id,
        task_type=TaskType.SUBTASK,
        title=subtask_data.title,
        description=subtask_data.description,
        assignee_id=subtask_data.assignee_id,
        priority=subtask_data.priority,
        start_date=subtask_data.start_date,
        due_date=subtask_data.due_date,
        labels=subtask_data.labels,
        tags=subtask_data.tags,
        visible_to_customer=subtask_data.visible_to_customer if subtask_data.visible_to_customer is not None else False,
    )

    db.add(subtask)
    await db.commit()
    await db.refresh(subtask)

    # Real-time notification to creator and assignee (if any)
    try:
        ws_payload = {
            "id": str(uuid.uuid4()),
            "title": f"Subtask created: {subtask.title}",
            "message": "A new subtask was created.",
            "notification_type": "system_alert",
            "created_at": datetime.utcnow().isoformat(),
            "context": {"task_id": subtask.id, "project_id": subtask.project_id, "parent_task_id": task_id, "event": "subtask_created"},
        }
        await ws_send_notification(current_user.id, current_user.organization_id, ws_payload)
        if subtask.assignee_id and subtask.assignee_id != current_user.id:
            await ws_send_notification(subtask.assignee_id, current_user.organization_id, ws_payload)
    except Exception:
        pass

    return subtask


# TASK COMMENTS ENDPOINTS

@router.get("/{task_id}/comments", response_model=List[dict])
async def get_task_comments(
    task_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get all comments for a task"""
    
    # Verify task access
    await verify_task_access(task_id, current_user, db)
    
    # Get comments with user info
    query = select(TaskComment).where(
        TaskComment.task_id == task_id
    ).order_by(TaskComment.created_at.asc())
    
    result = await db.execute(query)
    comments = result.scalars().all()
    
    # Format response with user data
    formatted_comments = []
    for comment in comments:
        # Get user info
        user_query = select(User).where(User.id == comment.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        formatted_comments.append({
            "id": comment.id,
            "task_id": comment.task_id,
            "user_id": comment.user_id,
            "content": comment.content,
            "parent_comment_id": comment.parent_comment_id,
            "mentions": comment.mentions or [],
            "linked_tasks": comment.linked_tasks or [],
            "is_edited": comment.is_edited,
            "is_deleted": comment.is_deleted,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "avatar_url": getattr(user, 'avatar_url', None)
            } if user else None
        })
    
    return formatted_comments


@router.post("/{task_id}/comments", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_task_comment(
    task_id: str,
    comment_data: TaskCommentCreate,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new comment for a task"""
    
    # Verify task access
    await verify_task_access(task_id, current_user, db)
    
    # Create comment
    comment = TaskComment(
        id=str(uuid.uuid4()),
        task_id=task_id,
        user_id=current_user.id,
        content=comment_data.content,
        parent_comment_id=comment_data.parent_comment_id,
        mentions=comment_data.mentions,
        linked_tasks=comment_data.linked_tasks
    )
    
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    
    # Format response
    formatted_comment = {
        "id": comment.id,
        "task_id": comment.task_id,
        "user_id": comment.user_id,
        "content": comment.content,
        "parent_comment_id": comment.parent_comment_id,
        "mentions": comment.mentions or [],
        "linked_tasks": comment.linked_tasks or [],
        "is_edited": comment.is_edited,
        "is_deleted": comment.is_deleted,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
        "user": {
            "id": current_user.id,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "email": current_user.email,
            "avatar_url": getattr(current_user, 'avatar_url', None)
        }
    }
    
    return formatted_comment


@router.post("/{task_id}/comments/with-files", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_task_comment_with_files(
    task_id: str,
    content: str = "",
    parent_comment_id: str = None,
    files: List[UploadFile] = File([]),
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new comment with file attachments for a task"""
    
    # Verify task access
    await verify_task_access(task_id, current_user, db)
    
    if not content.strip() and not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either content or files must be provided"
        )
    
    # Create comment
    comment = TaskComment(
        id=str(uuid.uuid4()),
        task_id=task_id,
        user_id=current_user.id,
        content=content.strip() or "Shared files",
        parent_comment_id=parent_comment_id if parent_comment_id else None,
        mentions=[],
        linked_tasks=[]
    )
    
    db.add(comment)
    await db.flush()  # Get comment ID for file uploads
    
    # Handle file attachments
    comment_attachments = []
    if files:
        # Create upload directory
        upload_dir = Path("uploads") / current_user.organization_id / "comments" / comment.id
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        for file in files:
            if file.filename:  # Ensure file has a name
                # Generate unique filename
                file_id = str(uuid.uuid4())
                file_extension = Path(file.filename or '').suffix
                filename = f"{file_id}{file_extension}"
                file_path = upload_dir / filename
                
                # Save file
                async with aiofiles.open(file_path, 'wb') as f:
                    file_content = await file.read()
                    await f.write(file_content)
                
                # Create attachment record
                attachment = TaskAttachment(
                    id=str(uuid.uuid4()),
                    task_id=task_id,
                    user_id=current_user.id,
                    filename=filename,
                    original_filename=file.filename,
                    file_path=str(file_path),
                    file_size=len(file_content),
                    mime_type=file.content_type
                )
                
                db.add(attachment)
                comment_attachments.append({
                    "id": attachment.id,
                    "filename": attachment.filename,
                    "original_filename": attachment.original_filename,
                    "file_size": attachment.file_size,
                    "mime_type": attachment.mime_type
                })
    
    await db.commit()
    await db.refresh(comment)
    
    # Format response
    formatted_comment = {
        "id": comment.id,
        "task_id": comment.task_id,
        "user_id": comment.user_id,
        "content": comment.content,
        "parent_comment_id": comment.parent_comment_id,
        "mentions": comment.mentions or [],
        "linked_tasks": comment.linked_tasks or [],
        "is_edited": comment.is_edited,
        "is_deleted": comment.is_deleted,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
        "attachments": comment_attachments,
        "user": {
            "id": current_user.id,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "email": current_user.email,
            "avatar_url": getattr(current_user, 'avatar_url', None)
        }
    }
    
    return formatted_comment


@router.delete("/{task_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_comment(
    task_id: str,
    comment_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a comment (soft delete)"""
    
    # Verify task access
    await verify_task_access(task_id, current_user, db)
    
    # Get comment
    query = select(TaskComment).where(
        (TaskComment.id == comment_id) &
        (TaskComment.task_id == task_id)
    )
    result = await db.execute(query)
    comment = result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    # Only allow deletion by comment author or task owner
    if comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this comment"
        )
    
    # Soft delete
    comment.is_deleted = True
    await db.commit()


# TASK ATTACHMENTS ENDPOINTS

@router.get("/{task_id}/attachments", response_model=List[dict])
async def get_task_attachments(
    task_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get all attachments for a task"""
    
    # Verify task access
    await verify_task_access(task_id, current_user, db)
    
    # Get attachments
    query = select(TaskAttachment).where(
        TaskAttachment.task_id == task_id
    ).order_by(TaskAttachment.created_at.desc())
    
    result = await db.execute(query)
    attachments = result.scalars().all()
    
    # Format response
    formatted_attachments = []
    for attachment in attachments:
        # Get user info
        user_query = select(User).where(User.id == attachment.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        formatted_attachments.append({
            "id": attachment.id,
            "task_id": attachment.task_id,
            "user_id": attachment.user_id,
            "filename": attachment.filename,
            "original_filename": attachment.original_filename,
            "file_path": attachment.file_path,
            "file_size": attachment.file_size,
            "mime_type": attachment.mime_type,
            "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
            "updated_at": attachment.updated_at.isoformat() if attachment.updated_at else None,
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "avatar_url": getattr(user, 'avatar_url', None)
            } if user else None
        })
    
    return formatted_attachments


@router.post("/{task_id}/attachments", response_model=dict, status_code=status.HTTP_201_CREATED)
async def upload_task_attachment(
    task_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Upload an attachment for a task"""
    
    # Verify task access
    await verify_task_access(task_id, current_user, db)
    
    # Create upload directory
    upload_dir = Path("uploads") / current_user.organization_id / "tasks" / task_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    file_extension = Path(file.filename or '').suffix
    filename = f"{file_id}{file_extension}"
    file_path = upload_dir / filename
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Create attachment record
    attachment = TaskAttachment(
        id=str(uuid.uuid4()),
        task_id=task_id,
        user_id=current_user.id,
        filename=filename,
        original_filename=file.filename or filename,
        file_path=str(file_path),
        file_size=len(content),
        mime_type=file.content_type
    )
    
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    
    # Format response
    formatted_attachment = {
        "id": attachment.id,
        "task_id": attachment.task_id,
        "user_id": attachment.user_id,
        "filename": attachment.filename,
        "original_filename": attachment.original_filename,
        "file_path": attachment.file_path,
        "file_size": attachment.file_size,
        "mime_type": attachment.mime_type,
        "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
        "updated_at": attachment.updated_at.isoformat() if attachment.updated_at else None,
        "user": {
            "id": current_user.id,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "email": current_user.email,
            "avatar_url": getattr(current_user, 'avatar_url', None)
        }
    }
    
    return formatted_attachment


@router.get("/{task_id}/attachments/{attachment_id}/download")
async def download_task_attachment(
    task_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Download an attachment file"""
    # Verify task access and fetch attachment
    await verify_task_access(task_id, current_user, db)
    query = select(TaskAttachment).where(
        (TaskAttachment.id == attachment_id) & (TaskAttachment.task_id == task_id)
    )
    result = await db.execute(query)
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    if not os.path.exists(attachment.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on server")
    return FileResponse(
        path=attachment.file_path,
        filename=attachment.original_filename,
        media_type=attachment.mime_type or 'application/octet-stream'
    )

@router.delete("/{task_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_attachment(
    task_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete an attachment"""
    
    # Verify task access
    await verify_task_access(task_id, current_user, db)
    
    # Get attachment
    query = select(TaskAttachment).where(
        (TaskAttachment.id == attachment_id) &
        (TaskAttachment.task_id == task_id)
    )
    result = await db.execute(query)
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found"
        )
    
    # Only allow deletion by attachment owner
    if attachment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this attachment"
        )
    
    # Delete file from disk
    try:
        if os.path.exists(attachment.file_path):
            os.remove(attachment.file_path)
    except Exception:
        pass  # File deletion is best effort
    
    # Delete from database
    await db.delete(attachment)
    await db.commit()


# TASK DOCUMENTS ENDPOINTS

@router.get("/{task_id}/documents", response_model=List[dict])
async def get_task_documents(
    task_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get all documents for a task"""
    
    # Verify task access
    await verify_task_access(task_id, current_user, db)
    
    # Get documents
    query = select(TaskDocument).where(
        TaskDocument.task_id == task_id
    ).order_by(TaskDocument.created_at.desc())
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    # Format response
    formatted_documents = []
    for document in documents:
        # Get user info
        user_query = select(User).where(User.id == document.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        formatted_documents.append({
            "id": document.id,
            "task_id": document.task_id,
            "user_id": document.user_id,
            "title": document.title,
            "content": document.content,
            "document_type": document.document_type.value,
            "version": document.version,
            "is_template": document.is_template,
            "tags": document.tags or [],
            "metadata": document.document_metadata or {},
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None,
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "avatar_url": getattr(user, 'avatar_url', None)
            } if user else None
        })
    
    return formatted_documents


@router.post("/{task_id}/documents", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_task_document(
    task_id: str,
    document_data: TaskDocumentCreate,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new document for a task"""
    
    # Verify task access
    await verify_task_access(task_id, current_user, db)
    
    # Create document
    document = TaskDocument(
        id=str(uuid.uuid4()),
        task_id=task_id,
        user_id=current_user.id,
        title=document_data.title,
        content=document_data.content,
        document_type=document_data.document_type,
        is_template=document_data.is_template,
        tags=document_data.tags,
        document_metadata=document_data.metadata,
        version=1
    )
    
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    # Format response
    formatted_document = {
        "id": document.id,
        "task_id": document.task_id,
        "user_id": document.user_id,
        "title": document.title,
        "content": document.content,
        "document_type": document.document_type.value,
        "version": document.version,
        "is_template": document.is_template,
            "tags": document.tags or [],
            "metadata": document.document_metadata or {},
            "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        "user": {
            "id": current_user.id,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "email": current_user.email,
            "avatar_url": getattr(current_user, 'avatar_url', None)
        }
    }
    
    return formatted_document


@router.put("/{task_id}/documents/{document_id}", response_model=dict)
async def update_task_document(
    task_id: str,
    document_id: str,
    document_data: TaskDocumentUpdate,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a task document"""
    
    # Verify task access
    await verify_task_access(task_id, current_user, db)
    
    # Get document
    query = select(TaskDocument).where(
        (TaskDocument.id == document_id) &
        (TaskDocument.task_id == task_id)
    )
    result = await db.execute(query)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Only allow updates by document owner
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this document"
        )
    
    # Update document fields
    update_data = document_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "metadata":
            setattr(document, "document_metadata", value)
        else:
            setattr(document, field, value)
    
    # Increment version on content changes
    if "content" in update_data or "title" in update_data:
        document.version += 1
    
    await db.commit()
    await db.refresh(document)
    
    # Format response
    formatted_document = {
        "id": document.id,
        "task_id": document.task_id,
        "user_id": document.user_id,
        "title": document.title,
        "content": document.content,
        "document_type": document.document_type.value,
        "version": document.version,
        "is_template": document.is_template,
        "tags": document.tags or [],
        "metadata": document.document_metadata or {},
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        "user": {
            "id": current_user.id,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "email": current_user.email,
            "avatar_url": getattr(current_user, 'avatar_url', None)
        }
    }
    
    return formatted_document


@router.delete("/{task_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_document(
    task_id: str,
    document_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a document"""
    
    # Verify task access
    await verify_task_access(task_id, current_user, db)
    
    # Get document
    query = select(TaskDocument).where(
        (TaskDocument.id == document_id) &
        (TaskDocument.task_id == task_id)
    )
    result = await db.execute(query)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Only allow deletion by document owner
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this document"
        )
    
    # Delete from database
    await db.delete(document)
    await db.commit()


# TASK ACTIVITIES ENDPOINT

@router.get("/{task_id}/activities", response_model=List[ActivityItem])
async def get_task_activities(
    task_id: str,
    current_user: User = Depends(get_current_active_user_master),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get activity timeline for a task"""
    
    # Verify task access
    await verify_task_access(task_id, current_user, db)
    
    # For now, return a mock activity feed
    # In a real implementation, you'd have an activities table or audit log
    activities = []
    
    # Get comments as activities
    comments_query = select(TaskComment).where(TaskComment.task_id == task_id).order_by(TaskComment.created_at.desc())
    comments_result = await db.execute(comments_query)
    comments = comments_result.scalars().all()
    
    for comment in comments:
        user_query = select(User).where(User.id == comment.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if user:
            activities.append(ActivityItem(
                id=f"comment_{comment.id}",
                type="comment_added",
                title="added a comment",
                description=comment.content[:100] + "..." if len(comment.content) > 100 else comment.content,
                user_name=f"{user.first_name} {user.last_name}",
                user_avatar=getattr(user, 'avatar_url', None),
                created_at=comment.created_at.isoformat() if comment.created_at else ""
            ))

    # Get subtasks created as activities
    subtasks_query = select(TaskModel).where(TaskModel.parent_task_id == task_id).order_by(TaskModel.created_at.desc())
    subtasks_result = await db.execute(subtasks_query)
    subtasks = subtasks_result.scalars().all()

    for subtask in subtasks:
        user_query = select(User).where(User.id == subtask.created_by_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if user:
            activities.append(ActivityItem(
                id=f"subtask_{subtask.id}",
                type="subtask_created",
                title="created a subtask",
                description=subtask.title,
                user_name=f"{user.first_name} {user.last_name}",
                user_avatar=getattr(user, 'avatar_url', None),
                created_at=subtask.created_at.isoformat() if subtask.created_at else ""
            ))
    
    # Get attachments as activities
    attachments_query = select(TaskAttachment).where(TaskAttachment.task_id == task_id).order_by(TaskAttachment.created_at.desc())
    attachments_result = await db.execute(attachments_query)
    attachments = attachments_result.scalars().all()
    
    for attachment in attachments:
        user_query = select(User).where(User.id == attachment.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if user:
            activities.append(ActivityItem(
                id=f"attachment_{attachment.id}",
                type="attachment_added",
                title="uploaded a file",
                description=attachment.original_filename,
                user_name=f"{user.first_name} {user.last_name}",
                user_avatar=getattr(user, 'avatar_url', None),
                created_at=attachment.created_at.isoformat() if attachment.created_at else ""
            ))
    
    # Get documents as activities
    documents_query = select(TaskDocument).where(TaskDocument.task_id == task_id).order_by(TaskDocument.created_at.desc())
    documents_result = await db.execute(documents_query)
    documents = documents_result.scalars().all()
    
    for document in documents:
        user_query = select(User).where(User.id == document.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if user:
            activities.append(ActivityItem(
                id=f"document_{document.id}",
                type="document_created",
                title="created a document",
                description=document.title,
                user_name=f"{user.first_name} {user.last_name}",
                user_avatar=getattr(user, 'avatar_url', None),
                created_at=document.created_at.isoformat() if document.created_at else ""
            ))
    
    # Sort all activities by created_at
    activities.sort(key=lambda x: x.created_at, reverse=True)
    
    return activities
