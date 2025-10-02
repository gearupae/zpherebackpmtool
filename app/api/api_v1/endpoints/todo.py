from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime

from ....api.deps_tenant import get_tenant_db
from ....api.deps import get_current_active_user, get_current_organization
from ....models.user import User
from ....models.organization import Organization
from ....models.tenant.todo import NoteSection as NoteSectionModel, NoteTodo as NoteTodoModel
from ....schemas.todo import (
    NoteSection, NoteSectionCreate, NoteSectionUpdate,
    NoteTodo, NoteTodoCreate, NoteTodoUpdate
)

router = APIRouter()

async def ensure_todo_tables(db: AsyncSession) -> None:
    try:
        # Try a lightweight query
        await db.execute(select(NoteSectionModel).limit(1))
        await db.execute(select(NoteTodoModel).limit(1))
    except Exception:
        # Best-effort create tables if they don't exist
        from sqlalchemy import text
        try:
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS note_sections (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    notes TEXT,
                    user_id VARCHAR NOT NULL,
                    organization_id VARCHAR NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
            """))
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS note_todos (
                    id VARCHAR PRIMARY KEY,
                    section_id VARCHAR NOT NULL REFERENCES note_sections(id) ON DELETE CASCADE,
                    text TEXT NOT NULL,
                    done BOOLEAN DEFAULT FALSE,
                    position INTEGER DEFAULT 0,
                    user_id VARCHAR,
                    organization_id VARCHAR,
                    completed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
            """))
            await db.commit()
        except Exception:
            await db.rollback()
            # Swallow error; proper migrations should handle schema
            pass

# Sections
@router.get("/sections", response_model=List[NoteSection])
async def list_sections(
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
) -> Any:
    await ensure_todo_tables(db)
    q = select(NoteSectionModel).where(
        and_(
            NoteSectionModel.user_id == current_user.id,
            NoteSectionModel.organization_id == current_org.id,
        )
    ).order_by(NoteSectionModel.created_at.desc())
    res = await db.execute(q)
    return res.scalars().all()

@router.post("/sections", response_model=NoteSection, status_code=status.HTTP_201_CREATED)
async def create_section(
    data: NoteSectionCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
) -> Any:
    await ensure_todo_tables(db)
    section = NoteSectionModel(
        name=data.name,
        notes=data.notes,
        user_id=current_user.id,
        organization_id=current_org.id,
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section

@router.put("/sections/{section_id}", response_model=NoteSection)
async def update_section(
    section_id: str,
    data: NoteSectionUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
) -> Any:
    await ensure_todo_tables(db)
    q = select(NoteSectionModel).where(
        and_(
            NoteSectionModel.id == section_id,
            NoteSectionModel.user_id == current_user.id,
            NoteSectionModel.organization_id == current_org.id,
        )
    )
    res = await db.execute(q)
    section = res.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    if data.name is not None:
        section.name = data.name
    if data.notes is not None:
        section.notes = data.notes
    await db.commit()
    await db.refresh(section)
    return section

@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_section(
    section_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
) -> Response:
    await ensure_todo_tables(db)
    q = select(NoteSectionModel).where(
        and_(
            NoteSectionModel.id == section_id,
            NoteSectionModel.user_id == current_user.id,
            NoteSectionModel.organization_id == current_org.id,
        )
    )
    res = await db.execute(q)
    section = res.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    await db.delete(section)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Todos
@router.get("/sections/{section_id}/todos", response_model=List[NoteTodo])
async def list_todos(
    section_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
) -> Any:
    await ensure_todo_tables(db)
    s_q = select(NoteSectionModel.id).where(
        and_(
            NoteSectionModel.id == section_id,
            NoteSectionModel.user_id == current_user.id,
            NoteSectionModel.organization_id == current_org.id,
        )
    )
    if not (await db.execute(s_q)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Section not found")

    q = select(NoteTodoModel).where(NoteTodoModel.section_id == section_id).order_by(NoteTodoModel.position.desc(), NoteTodoModel.created_at.desc())
    res = await db.execute(q)
    return res.scalars().all()

@router.post("/sections/{section_id}/todos", response_model=NoteTodo, status_code=status.HTTP_201_CREATED)
async def create_todo(
    section_id: str,
    data: NoteTodoCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
) -> Any:
    await ensure_todo_tables(db)
    s_q = select(NoteSectionModel).where(
        and_(
            NoteSectionModel.id == section_id,
            NoteSectionModel.user_id == current_user.id,
            NoteSectionModel.organization_id == current_org.id,
        )
    )
    res = await db.execute(s_q)
    section = res.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    todo = NoteTodoModel(
        section_id=section_id,
        text=data.text,
        done=data.done,
        position=data.position,
        user_id=current_user.id,
        organization_id=current_org.id,
    )
    db.add(todo)
    await db.commit()
    await db.refresh(todo)
    return todo

@router.patch("/todos/{todo_id}", response_model=NoteTodo)
async def update_todo(
    todo_id: str,
    data: NoteTodoUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    await ensure_todo_tables(db)
    q = select(NoteTodoModel).where(
        and_(
            NoteTodoModel.id == todo_id,
            (NoteTodoModel.user_id == current_user.id) | (NoteTodoModel.user_id.is_(None))
        )
    )
    res = await db.execute(q)
    todo = res.scalar_one_or_none()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    if data.text is not None:
        todo.text = data.text
    if data.position is not None:
        todo.position = data.position
    if data.done is not None:
        todo.done = data.done
        todo.completed_at = datetime.utcnow() if data.done else None
    await db.commit()
    await db.refresh(todo)
    return todo

@router.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_todo(
    todo_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    await ensure_todo_tables(db)
    q = select(NoteTodoModel).where(
        and_(
            NoteTodoModel.id == todo_id,
            (NoteTodoModel.user_id == current_user.id) | (NoteTodoModel.user_id.is_(None))
        )
    )
    res = await db.execute(q)
    todo = res.scalar_one_or_none()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    await db.delete(todo)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
