from sqlalchemy import Column, String, Text, ForeignKey, JSON, Boolean, Integer
from sqlalchemy.orm import relationship
from .base import UUIDBaseModel


class ProjectComment(UUIDBaseModel):
    """Project comment model supporting both internal and public comments"""
    __tablename__ = "project_comments"
    
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)  # Nullable for public comments
    content = Column(Text, nullable=False)
    
    # Public comment support
    author_name = Column(String(100), nullable=True)  # For public comments
    author_email = Column(String(255), nullable=True)  # For public comments
    is_public = Column(Boolean, default=False, nullable=False)  # True for public comments
    is_approved = Column(Boolean, default=True, nullable=False)  # For moderation
    
    # Source tracking
    source_type = Column(String(50), default="internal", nullable=False)  # "internal", "public_share"
    share_id = Column(String(255), nullable=True, index=True)  # Share ID that generated this comment
    
    # Threading support
    parent_comment_id = Column(String, ForeignKey("project_comments.id"), nullable=True, index=True)
    
    # Mention support
    mentions = Column(JSON, default=list)  # List of user IDs mentioned
    
    # Task links
    linked_tasks = Column(JSON, default=list)  # List of task IDs linked in the comment
    
    # Flags
    is_edited = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    
    # Relationships
    project = relationship("Project", back_populates="comments")
    user = relationship("User")
    parent_comment = relationship("ProjectComment", remote_side="ProjectComment.id")
    replies = relationship("ProjectComment", back_populates="parent_comment", cascade="all, delete-orphan")
    attachments = relationship("ProjectCommentAttachment", back_populates="comment", cascade="all, delete-orphan")
    
    @property
    def display_author(self):
        """Get display name for the comment author"""
        if self.user:
            full_name = f"{self.user.first_name or ''} {self.user.last_name or ''}".strip()
            return full_name or self.user.email
        return self.author_name or "Anonymous"
    
    @property 
    def is_reply(self):
        """Check if this comment is a reply to another comment"""
        return self.parent_comment_id is not None
    
    def __repr__(self):
        author = self.display_author
        return f"<ProjectComment(project_id='{self.project_id}', author='{author}', public={self.is_public})>"


class ProjectCommentAttachment(UUIDBaseModel):
    """Project comment attachment model"""
    __tablename__ = "project_comment_attachments"
    
    comment_id = Column(String, ForeignKey("project_comments.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100))
    
    # Relationships
    comment = relationship("ProjectComment", back_populates="attachments")
    user = relationship("User")
    
    def __repr__(self):
        return f"<ProjectCommentAttachment(filename='{self.filename}', comment_id='{self.comment_id}')>"

