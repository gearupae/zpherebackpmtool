from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import UUIDBaseModel

class ProjectReportSchedule(UUIDBaseModel):
    __tablename__ = "project_report_schedules"

    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    day_of_month = Column(Integer, nullable=False, default=1)  # 1-28 typically
    recipients = Column(JSON, default=list)  # list of emails
    last_sent_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    project = relationship("Project")
