from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ....api.deps_tenant import (
    get_tenant_db as get_db,
    get_current_active_user_master as get_current_active_user,
    get_current_organization_master as get_current_organization,
)
from ....models.user import User
from ....models.organization import Organization
from ....models.project import Project
from ....models.task import Task
from ....models.knowledge_base import KnowledgeArticle, KnowledgeStatus, KnowledgeLink
from ....models.context_card import ContextCard
from ....models.decision_log import DecisionLog, DecisionStatus

router = APIRouter()


def _format_article(a: KnowledgeArticle) -> Dict[str, Any]:
    return {
        "id": a.id,
        "title": a.title,
        "summary": a.summary,
        "content_preview": (a.summary or (a.content[:140] + "…" if a.content else "")),
        "knowledge_type": a.knowledge_type.value if hasattr(a.knowledge_type, "value") else str(a.knowledge_type),
        "relevance_score": 0.75,
        "view_count": a.view_count,
        "created_at": a.created_at.isoformat() if getattr(a, "created_at", None) else None,
    }


def _format_context(c: ContextCard) -> Dict[str, Any]:
    return {
        "id": c.id,
        "title": c.title,
        "content_preview": (c.content[:140] + "…" if c.content else ""),
        "context_type": c.context_type,
        "impact_level": c.impact_level,
        "relevance_score": 0.7,
        "created_at": c.created_at.isoformat() if getattr(c, "created_at", None) else None,
    }


def _format_decision(d: DecisionLog) -> Dict[str, Any]:
    return {
        "id": d.id,
        "title": d.title,
        "summary": d.description[:140] + "…" if d.description else "",
        "decision_date": d.created_at.isoformat() if getattr(d, "created_at", None) else None,
        "relevance_score": 0.7,
    }


@router.get("/suggest-knowledge-for-project/{project_id}")
async def suggest_knowledge_for_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, List[Dict[str, Any]]]:
    # Verify project belongs to organization
    proj_res = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.organization_id == current_org.id))
    )
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Articles (published, for project or global)
    q_articles = (
        select(KnowledgeArticle)
        .where(
            and_(
                KnowledgeArticle.status == KnowledgeStatus.PUBLISHED,
                or_(KnowledgeArticle.project_id == project_id, KnowledgeArticle.project_id.is_(None)),
            )
        )
        .order_by(func.coalesce(KnowledgeArticle.published_at, KnowledgeArticle.created_at).desc())
        .limit(20)
    )
    art_res = await db.execute(q_articles)
    articles = [
        _format_article(a) for a in art_res.scalars().all()
    ]

    # Context cards for project
    q_context = (
        select(ContextCard)
        .options(selectinload(ContextCard.project))
        .where(ContextCard.project_id == project_id)
        .order_by(ContextCard.created_at.desc())
        .limit(20)
    )
    ctx_res = await db.execute(q_context)
    context_cards = [_format_context(c) for c in ctx_res.scalars().all()]

    # Decisions for project
    q_decisions = (
        select(DecisionLog)
        .options(selectinload(DecisionLog.project))
        .where(DecisionLog.project_id == project_id)
        .order_by(DecisionLog.decision_number.desc())
        .limit(20)
    )
    dec_res = await db.execute(q_decisions)
    decisions = [_format_decision(d) for d in dec_res.scalars().all()]

    return {"articles": articles, "context_cards": context_cards, "decisions": decisions}


@router.get("/suggest-knowledge-for-task/{task_id}")
async def suggest_knowledge_for_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, List[Dict[str, Any]]]:
    # Verify task belongs to user's organization via project
    t_res = await db.execute(select(Task).options(selectinload(Task.project)).where(Task.id == task_id))
    task = t_res.scalar_one_or_none()
    if not task or not task.project or task.project.organization_id != current_org.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    project_id = task.project_id

    # Reuse project suggestion logic
    data = await suggest_knowledge_for_project(project_id, current_user, current_org, db)  # type: ignore
    return data


@router.post("/auto-link-project-to-knowledge")
async def auto_link_project_to_knowledge(
    payload: Dict[str, str],
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    project_id = payload.get("project_id")
    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_id is required")

    # Verify project
    proj_res = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.organization_id == current_org.id))
    )
    if not proj_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    suggestions = await suggest_knowledge_for_project(project_id, current_user, current_org, db)  # type: ignore
    created: List[Dict[str, Any]] = []

    # Helper to insert link if not exists
    async def link_article(article_id: str):
        exists_res = await db.execute(
            select(KnowledgeLink).where(
                and_(KnowledgeLink.article_id == article_id, KnowledgeLink.project_id == project_id)
            )
        )
        if exists_res.scalar_one_or_none():
            return
        link = KnowledgeLink(
            article_id=article_id,
            project_id=project_id,
            link_type="references",
            relevance_score=7,
            created_by_id=current_user.id,
            auto_generated=True,
        )
        db.add(link)
        await db.flush()
        created.append({"article_id": article_id, "project_id": project_id})

    # Create links for top-N articles (e.g., 5)
    for a in suggestions.get("articles", [])[:5]:
        await link_article(a["id"])  # type: ignore

    await db.commit()
    return created


@router.post("/auto-link-task-to-knowledge")
async def auto_link_task_to_knowledge(
    payload: Dict[str, str],
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    task_id = payload.get("task_id")
    if not task_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task_id is required")

    t_res = await db.execute(select(Task).options(selectinload(Task.project)).where(Task.id == task_id))
    task = t_res.scalar_one_or_none()
    if not task or not task.project or task.project.organization_id != current_org.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    suggestions = await suggest_knowledge_for_task(task_id, current_user, current_org, db)  # type: ignore
    created: List[Dict[str, Any]] = []

    async def link_article(article_id: str):
        exists_res = await db.execute(
            select(KnowledgeLink).where(
                and_(KnowledgeLink.article_id == article_id, KnowledgeLink.task_id == task_id)
            )
        )
        if exists_res.scalar_one_or_none():
            return
        link = KnowledgeLink(
            article_id=article_id,
            task_id=task_id,
            link_type="references",
            relevance_score=7,
            created_by_id=current_user.id,
            auto_generated=True,
        )
        db.add(link)
        await db.flush()
        created.append({"article_id": article_id, "task_id": task_id})

    for a in suggestions.get("articles", [])[:5]:
        await link_article(a["id"])  # type: ignore

    await db.commit()
    return created