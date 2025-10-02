from pydantic import BaseModel
from datetime import datetime


class TaskDependencyBase(BaseModel):
    dependency_type: str = "blocks"  # blocks, follows, relates_to


class TaskDependencyCreate(TaskDependencyBase):
    dependent_task_id: str


class TaskDependencyUpdate(BaseModel):
    dependency_type: str


class TaskDependencyResponse(TaskDependencyBase):
    id: str
    prerequisite_task_id: str
    dependent_task_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
