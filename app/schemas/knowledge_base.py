from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from ..models.knowledge_base import KnowledgeType, KnowledgeStatus


class KnowledgeArticleBase(BaseModel):
    title: str
    content: str
    summary: Optional[str] = None
    knowledge_type: KnowledgeType
    category: Optional[str] = None
    subcategory: Optional[str] = None
    tags: Optional[List[str]] = []
    keywords: Optional[List[str]] = []
    difficulty_level: Optional[str] = "beginner"
    estimated_read_time: Optional[int] = 5
    contributors: Optional[List[str]] = []
    related_tasks: Optional[List[str]] = []
    related_decisions: Optional[List[str]] = []
    related_articles: Optional[List[str]] = []
    external_links: Optional[List[str]] = []
    attachments: Optional[List[str]] = []
    is_public: Optional[bool] = False
    access_groups: Optional[List[str]] = []


class KnowledgeArticleCreate(KnowledgeArticleBase):
    project_id: Optional[str] = None


class KnowledgeArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    knowledge_type: Optional[KnowledgeType] = None
    status: Optional[KnowledgeStatus] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    tags: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    difficulty_level: Optional[str] = None
    estimated_read_time: Optional[int] = None
    contributors: Optional[List[str]] = None
    reviewer_id: Optional[str] = None
    version: Optional[str] = None
    related_tasks: Optional[List[str]] = None
    related_decisions: Optional[List[str]] = None
    related_articles: Optional[List[str]] = None
    external_links: Optional[List[str]] = None
    attachments: Optional[List[str]] = None
    is_public: Optional[bool] = None
    access_groups: Optional[List[str]] = None
    next_review_date: Optional[datetime] = None


class KnowledgeArticle(KnowledgeArticleBase):
    id: str
    project_id: Optional[str]
    status: KnowledgeStatus
    author_id: str
    reviewer_id: Optional[str]
    version: str
    previous_version_id: Optional[str]
    view_count: int
    helpful_votes: int
    not_helpful_votes: int
    published_at: Optional[datetime]
    last_reviewed_at: Optional[datetime]
    next_review_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeArticleResponse(KnowledgeArticle):
    """Response model with additional computed fields"""
    author_name: Optional[str] = None
    reviewer_name: Optional[str] = None
    project_name: Optional[str] = None
    contributor_names: Optional[List[str]] = []
    helpfulness_score: Optional[float] = None
    
    class Config:
        from_attributes = True


class KnowledgeLinkBase(BaseModel):
    article_id: str
    task_id: Optional[str] = None
    project_id: Optional[str] = None
    decision_id: Optional[str] = None
    context_card_id: Optional[str] = None
    link_type: str
    relevance_score: Optional[int] = 5


class KnowledgeLinkCreate(KnowledgeLinkBase):
    pass


class KnowledgeLinkUpdate(BaseModel):
    link_type: Optional[str] = None
    relevance_score: Optional[int] = None


class KnowledgeLink(KnowledgeLinkBase):
    id: str
    created_by_id: str
    auto_generated: bool
    confidence_score: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True





