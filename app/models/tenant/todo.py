from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..base import UUIDBaseModel

class NoteSection(UUIDBaseModel):
    __tablename__ = "note_sections"

    name = Column(String(255), nullable=False)
    notes = Column(Text)

    # Ownership / tenancy
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)

    # Relationships
    todos = relationship("NoteTodo", back_populates="section", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<NoteSection(name='{self.name}', user='{self.user_id}')>"


class NoteTodo(UUIDBaseModel):
    __tablename__ = "note_todos"

    section_id = Column(String, ForeignKey("note_sections.id"), nullable=False)
    text = Column(Text, nullable=False)
    done = Column(Boolean, default=False)
    position = Column(Integer, default=0)

    # Ownership (duplicate for quicker filters if needed)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)

    # Timestamps
    completed_at = Column(DateTime(timezone=True))

    # Relationships
    section = relationship("NoteSection", back_populates="todos")

    def __repr__(self) -> str:
        return f"<NoteTodo(text='{self.text[:20]}', done='{self.done}')>"
