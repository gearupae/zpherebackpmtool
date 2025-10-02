from sqlalchemy import Column, String, Text, DateTime, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .base import UUIDBaseModel

class AIRisk(UUIDBaseModel):
    __tablename__ = "ai_risks"
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    risk_type = Column(String, nullable=False)  # schedule, budget, resource, quality
    score = Column(Float, default=0.0)
    severity = Column(String, default="low")  # low, medium, high, critical
    explanation = Column(Text)
    factors = Column(JSON, default=dict)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String, ForeignKey("users.id"))

class AIInsight(UUIDBaseModel):
    __tablename__ = "ai_insights"
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    category = Column(String, nullable=False)  # anomaly, trend, recommendation
    message = Column(Text, nullable=False)
    details = Column(JSON, default=dict)

class AIMeetingSummary(UUIDBaseModel):
    __tablename__ = "ai_meeting_summaries"
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    source_type = Column(String, default="meeting")  # meeting, email, chat
    source_id = Column(String)  # optional pointer to a meeting/chat record
    summary = Column(Text)
    action_items = Column(JSON, default=list)  # list of {title, assignee_id, due_date}
    decisions = Column(JSON, default=list)
    sentiments = Column(JSON, default=dict)

class AIScenario(UUIDBaseModel):
    __tablename__ = "ai_scenarios"
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    title = Column(String, nullable=False)
    assumptions = Column(JSON, default=dict)  # {scope_change, budget_delta, resource_loss}
    impact = Column(JSON, default=dict)  # {timeline_impact_days, budget_impact, risk_delta}
    recommendation = Column(Text)

class AIForecast(UUIDBaseModel):
    __tablename__ = "ai_forecasts"
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    forecast_type = Column(String, default="timeline")  # timeline, budget
    inputs = Column(JSON, default=dict)
    outputs = Column(JSON, default=dict)  # {finish_date, confidence, burn_rate, etc}

