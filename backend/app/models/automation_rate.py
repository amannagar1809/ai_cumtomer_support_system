"""Automation rate metrics models."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class AutomationRate(Base):
    """Automation rate model for tracking AI ROI."""

    __tablename__ = "automation_rate"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    conversation_id = Column(PG_UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Automation type
    automation_type = Column(String(20), nullable=False)  # fully_automated, hybrid, human_only
    
    # Conversation metrics
    total_messages = Column(Integer, nullable=False, default=0)
    ai_messages = Column(Integer, nullable=False, default=0)
    human_messages = Column(Integer, nullable=False, default=0)
    conversation_duration_seconds = Column(Float, nullable=True)
    
    # Intent and category
    intent_category = Column(String(100), nullable=True)  # For target tracking
    predicted_intent = Column(String(100), nullable=True)
    
    # Cost estimation
    estimated_human_time_minutes = Column(Float, nullable=True)  # Estimated time if handled by human
    actual_human_time_minutes = Column(Float, nullable=True)  # Actual human time spent
    agent_cost_per_hour = Column(Float, nullable=False, default=25.0)  # Default $25/hour
    cost_savings = Column(Float, nullable=True)  # Calculated savings
    
    # Context
    channel = Column(String(50), nullable=False)  # web, voice, email, chat
    language = Column(String(10), nullable=False)
    
    # Targets
    automation_target = Column(Float, nullable=True)  # Target automation rate for this category
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AutomationRate(id={self.id}, type={self.automation_type}, savings={self.cost_savings})>"
