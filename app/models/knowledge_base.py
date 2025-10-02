from sqlalchemy import Column, String, Text, ForeignKey, JSON, Boolean, DateTime, Enum as SQLEnum, Integer
from sqlalchemy.orm import relationship
from enum import Enum
from datetime import datetime
from .base import UUIDBaseModel


class KnowledgeType(str, Enum):
    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    FAQ = "faq"
    BEST_PRACTICE = "best_practice"
    LESSON_LEARNED = "lesson_learned"
    TROUBLESHOOTING = "troubleshooting"
    PROCESS = "process"
    TEMPLATE = "template"
    REFERENCE = "reference"


class KnowledgeStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    OUTDATED = "outdated"


class KnowledgeArticle(UUIDBaseModel):
    """Knowledge base article model"""
    __tablename__ = "knowledge_articles"

    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text)  # Brief summary
    
    # Classification
    knowledge_type = Column(SQLEnum(KnowledgeType), nullable=False)
    status = Column(SQLEnum(KnowledgeStatus), default=KnowledgeStatus.DRAFT)
    category = Column(String(100))  # Custom category
    subcategory = Column(String(100))  # Custom subcategory
    
    # Metadata
    tags = Column(JSON, default=list)  # Searchable tags
    keywords = Column(JSON, default=list)  # Search keywords
    difficulty_level = Column(String(20), default="beginner")  # beginner, intermediate, advanced
    estimated_read_time = Column(Integer, default=5)  # In minutes
    
    # Authoring
    author_id = Column(String, ForeignKey("users.id"), nullable=False)
    contributors = Column(JSON, default=list)  # List of contributor user IDs
    reviewer_id = Column(String, ForeignKey("users.id"))
    
    # Versioning
    version = Column(String(20), default="1.0")
    previous_version_id = Column(String, ForeignKey("knowledge_articles.id"))
    
    # Relationships and links
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    related_tasks = Column(JSON, default=list)  # List of related task IDs
    related_decisions = Column(JSON, default=list)  # List of related decision IDs
    related_articles = Column(JSON, default=list)  # List of related article IDs
    
    # External links
    external_links = Column(JSON, default=list)  # External documentation links
    attachments = Column(JSON, default=list)  # File attachments
    
    # Usage tracking
    view_count = Column(Integer, default=0)
    helpful_votes = Column(Integer, default=0)
    not_helpful_votes = Column(Integer, default=0)
    
    # Publishing
    published_at = Column(DateTime)
    last_reviewed_at = Column(DateTime)
    next_review_date = Column(DateTime)
    
    # Accessibility
    is_public = Column(Boolean, default=False)  # Visible to all organization members
    access_groups = Column(JSON, default=list)  # Specific group access
    
    # Relationships
    project = relationship("Project", back_populates="knowledge_articles")
    author = relationship("User", foreign_keys=[author_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    previous_version = relationship("KnowledgeArticle", remote_side="KnowledgeArticle.id")

    def __repr__(self):
        return f"<KnowledgeArticle(title='{self.title}', type='{self.knowledge_type}')>"


class KnowledgeLink(UUIDBaseModel):
    """Links between knowledge articles and other entities"""
    __tablename__ = "knowledge_links"

    # Source and target
    article_id = Column(String, ForeignKey("knowledge_articles.id"), nullable=False)
    
    # Linkable entities (one of these will be populated)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    decision_id = Column(String, ForeignKey("decision_logs.id"), nullable=True)
    context_card_id = Column(String, ForeignKey("context_cards.id"), nullable=True)
    
    # Link metadata
    link_type = Column(String(50), nullable=False)  # references, supports, explains, etc.
    relevance_score = Column(Integer, default=5)  # 1-10 relevance rating
    created_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Auto-linking
    auto_generated = Column(Boolean, default=False)
    confidence_score = Column(String(20))  # Auto-link confidence
    
    # Relationships
    article = relationship("KnowledgeArticle")
    task = relationship("Task")
    project = relationship("Project")
    created_by = relationship("User")

    def __repr__(self):
        return f"<KnowledgeLink(article_id='{self.article_id}', type='{self.link_type}')>"





