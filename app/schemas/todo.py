from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class NoteTodoBase(BaseModel):
    text: str = Field(..., min_length=1)
    done: bool = False
    position: int = 0

class NoteTodoCreate(NoteTodoBase):
    pass

class NoteTodoUpdate(BaseModel):
    text: Optional[str] = None
    done: Optional[bool] = None
    position: Optional[int] = None

class NoteTodo(NoteTodoBase):
    id: str
    section_id: str
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class NoteSectionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    notes: Optional[str] = None

class NoteSectionCreate(NoteSectionBase):
    pass

class NoteSectionUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None

class NoteSection(NoteSectionBase):
    id: str
    todos: List[NoteTodo] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
