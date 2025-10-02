from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
import uuid
import re
import os
import aiofiles
from datetime import datetime

from ....db.database import get_db
from ...deps_tenant import get_tenant_db
from ....models.user import User
from ....models.project import Project
from ....models.project_comment import ProjectComment, ProjectCommentAttachment
from ....models.organization import Organization
from ....schemas.project_comment import ProjectCommentCreate, ProjectCommentUpdate, ProjectComment as ProjectCommentSchema, ProjectCommentResponse
from ...deps import get_current_active_user, get_current_organization

router = APIRouter()


def extract_mentions_and_task_links(content: str) -> tuple[List[str], List[str]]:
    """Extract @mentions and task links from comment content"""
    # Extract @mentions (assuming format @username or @user_id)
    mention_pattern = r'@([a-zA-Z0-9_.-]+)'
    mentions = re.findall(mention_pattern, content)
    
    # Extract task links (assuming format #TASK-123 or #task_id)
    task_link_pattern = r'#([a-zA-Z0-9-]+)'
    task_links = re.findall(task_link_pattern, content)
    
    return mentions, task_links


@router.get("/projects/{project_id}/comments", response_model=List[ProjectCommentSchema])
async def get_project_comments(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get all comments for a project"""
    
    # Verify project exists and user has access
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
    
    # Get comments with user info and attachments, ordered by creation date
    comments_result = await db.execute(
        select(ProjectComment)
        .options(
            selectinload(ProjectComment.user),
            selectinload(ProjectComment.attachments)
        )
        .where(
            and_(
                ProjectComment.project_id == project_id,
                ProjectComment.is_deleted == False,
                ProjectComment.parent_comment_id == None  # Top-level comments only
            )
        )
        .order_by(ProjectComment.created_at.desc())
    )
    comments = comments_result.scalars().all()
    
    # Get all replies for the comments
    comment_ids = [comment.id for comment in comments]
    if comment_ids:
        replies_result = await db.execute(
            select(ProjectComment)
            .options(
                selectinload(ProjectComment.user),
                selectinload(ProjectComment.attachments)
            )
            .where(
                and_(
                    ProjectComment.parent_comment_id.in_(comment_ids),
                    ProjectComment.is_deleted == False
                )
            )
            .order_by(ProjectComment.created_at.asc())
        )
        replies_by_parent = {}
        for reply in replies_result.scalars().all():
            parent_id = reply.parent_comment_id
            if parent_id not in replies_by_parent:
                replies_by_parent[parent_id] = []
            replies_by_parent[parent_id].append(reply)
        
        # Assign replies to their parent comments
        for comment in comments:
            comment.replies = replies_by_parent.get(comment.id, [])
    
    return comments


@router.post("/projects/{project_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_project_comment(
    project_id: str,
    comment_data: ProjectCommentCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new project comment"""
    
    # Verify project exists and user has access
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
    
    # Verify parent comment exists if provided
    if comment_data.parent_comment_id:
        parent_result = await db.execute(
            select(ProjectComment).where(
                and_(
                    ProjectComment.id == comment_data.parent_comment_id,
                    ProjectComment.project_id == project_id,
                    ProjectComment.is_deleted == False
                )
            )
        )
        if not parent_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent comment not found"
            )
    
    # Extract mentions and task links from content
    mentions, task_links = extract_mentions_and_task_links(comment_data.content)
    
    # Create comment
    comment = ProjectComment(
        id=str(uuid.uuid4()),
        project_id=project_id,
        user_id=current_user.id,
        content=comment_data.content,
        parent_comment_id=comment_data.parent_comment_id,
        mentions=mentions + (comment_data.mentions or []),
        linked_tasks=task_links + (comment_data.linked_tasks or [])
    )
    
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    
    # Handle attachments if provided
    attachments_data = []
    if comment_data.attachment_ids:
        # For now, we'll assume the attachment_ids are file paths from a previous upload
        # In a real implementation, you might get these from a temporary file storage
        for attachment_id in comment_data.attachment_ids:
            # This is a placeholder - in reality, you'd retrieve file info from temp storage
            # For testing, we'll create dummy attachment records
            pass
    
    # Return a simple response to avoid serialization issues
    return {
        "id": comment.id,
        "content": comment.content,
        "project_id": comment.project_id,
        "user_id": comment.user_id,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "full_name": f"{current_user.first_name} {current_user.last_name}"
        },
        "is_edited": comment.is_edited,
        "is_deleted": comment.is_deleted,
        "attachments": attachments_data
    }


@router.put("/projects/{project_id}/comments/{comment_id}", response_model=ProjectCommentSchema)
async def update_project_comment(
    project_id: str,
    comment_id: str,
    comment_data: ProjectCommentUpdate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update a project comment"""
    
    # Get comment and verify permissions
    comment_result = await db.execute(
        select(ProjectComment)
        .options(selectinload(ProjectComment.user))
        .where(
            and_(
                ProjectComment.id == comment_id,
                ProjectComment.project_id == project_id,
                ProjectComment.is_deleted == False
            )
        )
    )
    comment = comment_result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    # Only comment author or project owner can edit
    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one()
    
    if comment.user_id != current_user.id and project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to edit this comment"
        )
    
    # Update comment
    if comment_data.content is not None:
        comment.content = comment_data.content
        comment.is_edited = True
        
        # Re-extract mentions and task links
        mentions, task_links = extract_mentions_and_task_links(comment_data.content)
        comment.mentions = mentions + (comment_data.mentions or [])
        comment.linked_tasks = task_links + (comment_data.linked_tasks or [])
    
    if comment_data.is_deleted is not None:
        comment.is_deleted = comment_data.is_deleted
    
    await db.commit()
    await db.refresh(comment)
    
    return comment


@router.delete("/projects/{project_id}/comments/{comment_id}")
async def delete_project_comment(
    project_id: str,
    comment_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Delete a project comment (soft delete)"""
    
    # Get comment and verify permissions
    comment_result = await db.execute(
        select(ProjectComment).where(
            and_(
                ProjectComment.id == comment_id,
                ProjectComment.project_id == project_id,
                ProjectComment.is_deleted == False
            )
        )
    )
    comment = comment_result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    # Only comment author or project owner can delete
    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one()
    
    if comment.user_id != current_user.id and project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this comment"
        )
    
    # Soft delete
    comment.is_deleted = True
    await db.commit()
    
    return {"message": "Comment deleted successfully"}


@router.post("/projects/{project_id}/comments/with-files", status_code=status.HTTP_201_CREATED)
async def create_comment_with_files(
    project_id: str,
    content: str = Form(...),
    parent_comment_id: str = Form(None),
    files: List[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new project comment with file attachments"""
    
    # Verify project exists and user has access
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
    
    # Extract mentions and task links from content
    mentions, task_links = extract_mentions_and_task_links(content)
    
    # Create comment
    comment = ProjectComment(
        id=str(uuid.uuid4()),
        project_id=project_id,
        user_id=current_user.id,
        content=content,
        parent_comment_id=parent_comment_id,
        mentions=mentions,
        linked_tasks=task_links
    )
    
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    
    # Handle file attachments
    attachments_data = []
    if files:
        # Create uploads directory if it doesn't exist
        upload_dir = f"uploads/{current_org.id}/comments"
        os.makedirs(upload_dir, exist_ok=True)
        
        for file in files:
            if file.filename:
                # Generate unique filename
                file_id = str(uuid.uuid4())
                file_extension = os.path.splitext(file.filename)[1]
                unique_filename = f"{file_id}{file_extension}"
                file_path = os.path.join(upload_dir, unique_filename)
                
                # Save file to disk
                async with aiofiles.open(file_path, 'wb') as f:
                    content = await file.read()
                    await f.write(content)
                
                # Create attachment record
                attachment = ProjectCommentAttachment(
                    id=file_id,
                    comment_id=comment.id,
                    user_id=current_user.id,
                    filename=unique_filename,
                    original_filename=file.filename,
                    file_path=file_path,
                    file_size=len(content),
                    mime_type=file.content_type
                )
                
                db.add(attachment)
                
                attachments_data.append({
                    "id": attachment.id,
                    "filename": attachment.filename,
                    "original_filename": attachment.original_filename,
                    "file_size": attachment.file_size,
                    "mime_type": attachment.mime_type
                })
        
        await db.commit()
    
    # Return response
    return {
        "id": comment.id,
        "content": comment.content,
        "project_id": comment.project_id,
        "user_id": comment.user_id,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "full_name": f"{current_user.first_name} {current_user.last_name}"
        },
        "is_edited": comment.is_edited,
        "is_deleted": comment.is_deleted,
        "attachments": attachments_data
    }
