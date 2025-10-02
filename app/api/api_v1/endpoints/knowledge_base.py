from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from ....api.deps_tenant import get_tenant_db as get_db
from ....models.user import User
from ....models.organization import Organization
from ....models.knowledge_base import KnowledgeArticle, KnowledgeLink, KnowledgeStatus
from ....models.project import Project
from ....models.task import Task
from ....schemas.knowledge_base import (
    KnowledgeArticleCreate,
    KnowledgeArticleUpdate,
    KnowledgeArticle as KnowledgeArticleSchema,
    KnowledgeArticleResponse,
    KnowledgeLinkCreate,
    KnowledgeLinkUpdate,
    KnowledgeLink as KnowledgeLinkSchema
)
from ...deps import get_current_active_user, get_current_organization

router = APIRouter()


@router.post("/articles/", response_model=KnowledgeArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_article(
    article_data: KnowledgeArticleCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new knowledge article"""
    # Verify project belongs to organization if specified
    if article_data.project_id:
        project_result = await db.execute(
            select(Project).where(
                and_(
                    Project.id == article_data.project_id,
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

    # Create knowledge article
    article = KnowledgeArticle(
        **article_data.model_dump(),
        author_id=current_user.id
    )
    
    db.add(article)
    await db.commit()
    await db.refresh(article)
    
    return await _enrich_article_response(article, db)


@router.get("/articles/", response_model=List[KnowledgeArticleResponse])
async def get_knowledge_articles(
    project_id: Optional[str] = None,
    knowledge_type: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[KnowledgeStatus] = None,
    search: Optional[str] = None,
    is_public: Optional[bool] = None,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get knowledge articles with filtering and search"""
    query = select(KnowledgeArticle).options(
        selectinload(KnowledgeArticle.project),
        selectinload(KnowledgeArticle.author),
        selectinload(KnowledgeArticle.reviewer)
    )
    
    conditions = []
    
    if project_id:
        # Verify project belongs to organization
        project_result = await db.execute(
            select(Project).where(
                and_(
                    Project.id == project_id,
                    Project.organization_id == current_org.id
                )
            )
        )
        if not project_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        conditions.append(KnowledgeArticle.project_id == project_id)
    else:
        # Filter by organization's projects or articles without project
        org_projects_subquery = select(Project.id).where(
            Project.organization_id == current_org.id
        )
        conditions.append(
            or_(
                KnowledgeArticle.project_id.in_(org_projects_subquery),
                KnowledgeArticle.project_id.is_(None)
            )
        )
    
    if knowledge_type:
        conditions.append(KnowledgeArticle.knowledge_type == knowledge_type)
        
    if category:
        conditions.append(KnowledgeArticle.category == category)
        
    if status:
        conditions.append(KnowledgeArticle.status == status)
    else:
        # Default: show published articles OR drafts authored/reviewed by current user
        conditions.append(
            or_(
                KnowledgeArticle.status == KnowledgeStatus.PUBLISHED,
                KnowledgeArticle.author_id == current_user.id,
                KnowledgeArticle.reviewer_id == current_user.id,
            )
        )
        
    if is_public is not None:
        conditions.append(KnowledgeArticle.is_public == is_public)
    
    if search:
        search_term = f"%{search}%"
        conditions.append(
            or_(
                KnowledgeArticle.title.ilike(search_term),
                KnowledgeArticle.content.ilike(search_term),
                KnowledgeArticle.summary.ilike(search_term)
            )
        )
    
    query = query.where(and_(*conditions)).order_by(
        KnowledgeArticle.created_at.desc()
    ).limit(limit).offset(offset)
    
    result = await db.execute(query)
    articles = result.scalars().all()
    
    return [await _enrich_article_response(article, db) for article in articles]


@router.get("/articles/{article_id}", response_model=KnowledgeArticleResponse)
async def get_knowledge_article(
    article_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get a specific knowledge article and increment view count"""
    article = await _get_article_or_404(article_id, current_org.id, db)
    
    # Increment view count
    article.view_count += 1
    await db.commit()
    
    return await _enrich_article_response(article, db)


@router.put("/articles/{article_id}", response_model=KnowledgeArticleResponse)
async def update_knowledge_article(
    article_id: str,
    article_update: KnowledgeArticleUpdate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update a knowledge article"""
    article = await _get_article_or_404(article_id, current_org.id, db)
    
    # Check if user can edit (author or reviewer)
    if article.author_id != current_user.id and article.reviewer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to edit this article"
        )
    
    # Update article
    for field, value in article_update.model_dump(exclude_unset=True).items():
        setattr(article, field, value)
    
    await db.commit()
    await db.refresh(article)
    
    return await _enrich_article_response(article, db)


@router.post("/articles/{article_id}/publish", response_model=KnowledgeArticleResponse)
async def publish_article(
    article_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Publish a knowledge article"""
    article = await _get_article_or_404(article_id, current_org.id, db)
    
    # Check authorization
    if article.author_id != current_user.id and article.reviewer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to publish this article"
        )
    
    article.status = KnowledgeStatus.PUBLISHED
    article.published_at = func.now()
    
    await db.commit()
    await db.refresh(article)
    
    return await _enrich_article_response(article, db)


@router.post("/articles/{article_id}/vote", response_model=KnowledgeArticleResponse)
async def vote_on_article(
    article_id: str,
    helpful: bool,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Vote on article helpfulness"""
    article = await _get_article_or_404(article_id, current_org.id, db)
    
    if helpful:
        article.helpful_votes += 1
    else:
        article.not_helpful_votes += 1
    
    await db.commit()
    await db.refresh(article)
    
    return await _enrich_article_response(article, db)


@router.post("/links/", response_model=KnowledgeLinkSchema, status_code=status.HTTP_201_CREATED)
async def create_knowledge_link(
    link_data: KnowledgeLinkCreate,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a link between knowledge article and other entities"""
    # Verify article exists and is accessible
    article = await _get_article_or_404(link_data.article_id, current_org.id, db)
    
    # Verify linked entities belong to organization
    if link_data.project_id:
        project_result = await db.execute(
            select(Project).where(
                and_(
                    Project.id == link_data.project_id,
                    Project.organization_id == current_org.id
                )
            )
        )
        if not project_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
    
    if link_data.task_id:
        task_result = await db.execute(
            select(Task).join(Project).where(
                and_(
                    Task.id == link_data.task_id,
                    Project.organization_id == current_org.id
                )
            )
        )
        if not task_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

    # Create knowledge link
    link = KnowledgeLink(
        **link_data.model_dump(),
        created_by_id=current_user.id
    )
    
    db.add(link)
    await db.commit()
    await db.refresh(link)
    
    return link


@router.get("/articles/{article_id}/links", response_model=List[KnowledgeLinkSchema])
async def get_article_links(
    article_id: str,
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get all links for a knowledge article"""
    article = await _get_article_or_404(article_id, current_org.id, db)
    
    result = await db.execute(
        select(KnowledgeLink).where(
            KnowledgeLink.article_id == article_id
        ).order_by(KnowledgeLink.relevance_score.desc())
    )
    
    return result.scalars().all()


@router.get("/search", response_model=List[KnowledgeArticleResponse])
async def search_knowledge_base(
    q: str = Query(..., min_length=2),
    knowledge_type: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(10, le=50),
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Advanced search in knowledge base"""
    search_term = f"%{q}%"
    
    query = select(KnowledgeArticle).options(
        selectinload(KnowledgeArticle.project),
        selectinload(KnowledgeArticle.author)
    )
    
    conditions = [
        KnowledgeArticle.status == KnowledgeStatus.PUBLISHED,
        or_(
            KnowledgeArticle.title.ilike(search_term),
            KnowledgeArticle.content.ilike(search_term),
            KnowledgeArticle.summary.ilike(search_term),
            func.array_to_string(KnowledgeArticle.tags, ' ').ilike(search_term),
            func.array_to_string(KnowledgeArticle.keywords, ' ').ilike(search_term)
        )
    ]
    
    # Filter by organization
    org_projects_subquery = select(Project.id).where(
        Project.organization_id == current_org.id
    )
    conditions.append(
        or_(
            KnowledgeArticle.project_id.in_(org_projects_subquery),
            KnowledgeArticle.project_id.is_(None)
        )
    )
    
    if knowledge_type:
        conditions.append(KnowledgeArticle.knowledge_type == knowledge_type)
        
    if category:
        conditions.append(KnowledgeArticle.category == category)
    
    query = query.where(and_(*conditions)).order_by(
        KnowledgeArticle.view_count.desc(),
        KnowledgeArticle.helpful_votes.desc()
    ).limit(limit)
    
    result = await db.execute(query)
    articles = result.scalars().all()
    
    return [await _enrich_article_response(article, db) for article in articles]


async def _get_article_or_404(
    article_id: str, 
    organization_id: str, 
    db: AsyncSession
) -> KnowledgeArticle:
    """Get knowledge article or raise 404"""
    result = await db.execute(
        select(KnowledgeArticle)
        .options(
            selectinload(KnowledgeArticle.project),
            selectinload(KnowledgeArticle.author),
            selectinload(KnowledgeArticle.reviewer)
        )
        .outerjoin(Project)
        .where(
            and_(
                KnowledgeArticle.id == article_id,
                or_(
                    Project.organization_id == organization_id,
                    KnowledgeArticle.project_id.is_(None)  # Global articles
                )
            )
        )
    )
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge article not found"
        )
    return article


async def _enrich_article_response(
    article: KnowledgeArticle, 
    db: AsyncSession
) -> KnowledgeArticleResponse:
    """Enrich article with additional data"""
    response_data = {
        **article.__dict__,
        "author_name": None,
        "reviewer_name": None,
        "project_name": None,
        "contributor_names": [],
        "helpfulness_score": None,
    }
    
    if article.author:
        response_data["author_name"] = f"{article.author.first_name} {article.author.last_name}"
    
    if article.reviewer:
        response_data["reviewer_name"] = f"{article.reviewer.first_name} {article.reviewer.last_name}"
    
    if article.project:
        response_data["project_name"] = article.project.name
    
    # Calculate helpfulness score
    total_votes = article.helpful_votes + article.not_helpful_votes
    if total_votes > 0:
        response_data["helpfulness_score"] = article.helpful_votes / total_votes
    
    # Get contributor names
    if article.contributors:
        contributor_result = await db.execute(
            select(User).where(User.id.in_(article.contributors))
        )
        contributors = contributor_result.scalars().all()
        response_data["contributor_names"] = [f"{u.first_name} {u.last_name}" for u in contributors]
    
    return KnowledgeArticleResponse(**response_data)





