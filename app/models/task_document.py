from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Enum, Integer, JSON
from sqlalchemy.orm import relationship
import enum
from .base import UUIDBaseModel


class DocumentType(str, enum.Enum):
    NOTES = "notes"
    SPECIFICATION = "specification"
    REQUIREMENTS = "requirements"
    TEST_PLAN = "test_plan"
    DESIGN = "design"
    CHECKLIST = "checklist"
    MEETING_NOTES = "meeting_notes"
    TECHNICAL_DOC = "technical_doc"
    USER_GUIDE = "user_guide"
    OTHER = "other"


class TaskDocument(UUIDBaseModel):
    """Task document model for in-app document creation and management"""
    __tablename__ = "task_documents"
    
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    document_type = Column(Enum(DocumentType), default=DocumentType.NOTES)
    version = Column(Integer, default=1)
    is_template = Column(Boolean, default=False)
    
    # Categorization and search
    tags = Column(JSON, default=list)  # List of tag names
    document_metadata = Column(JSON, default=dict)  # Additional document metadata
    
    # Relationships
    task = relationship("Task", back_populates="documents")
    user = relationship("User")
    
    def __repr__(self):
        return f"<TaskDocument(title='{self.title}', task_id='{self.task_id}')>"