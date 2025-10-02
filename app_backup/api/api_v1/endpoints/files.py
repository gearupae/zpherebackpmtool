from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import uuid
import os
from pathlib import Path
from datetime import datetime

from ....db.database import get_db
from ....models.user import User
from ....models.project import Project
from ....models.organization import Organization
from ....core.config import settings
from ...deps import get_current_active_user, get_current_organization

router = APIRouter()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    project_id: str = Form(None),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Upload a file"""
    
    # Validate file size
    if file.size and file.size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {settings.MAX_FILE_SIZE_MB}MB limit"
        )
    
    # Validate project if provided
    if project_id:
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
    
    try:
        # Create upload directory if it doesn't exist
        upload_dir = Path(settings.UPLOAD_DIR) / current_org.id
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix if file.filename else ""
        filename = f"{file_id}{file_extension}"
        file_path = upload_dir / filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # TODO: Save file metadata to database
        file_info = {
            "id": file_id,
            "filename": file.filename,
            "original_filename": file.filename,
            "size": file.size,
            "content_type": file.content_type,
            "project_id": project_id,
            "uploaded_by": current_user.id,
            "organization_id": current_org.id,
            "file_path": str(file_path),
            "uploaded_at": datetime.utcnow().isoformat()
        }
        
        return file_info
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
) -> Any:
    """Get file information"""
    
    # TODO: Get file metadata from database
    # For now, return placeholder
    return {
        "id": file_id,
        "message": "File endpoint - implementation needed"
    }


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
) -> Any:
    """Delete a file"""
    
    # TODO: Implement file deletion
    return {"message": "File deleted"}


@router.get("/project/{project_id}")
async def get_project_files(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get files for a project"""
    
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
    
    # TODO: Get files from database
    return {
        "project_id": project_id,
        "files": []
    }
