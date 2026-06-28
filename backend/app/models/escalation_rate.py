"""Escalation rate metrics models."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class EscalationRate(Base):
    """Escalation rate model for tracking AI effectiveness."""

    __tablename__ = "escalation_rate"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    conversation_id = Column(PG_UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Escalation tracking
    is_escalated = Column(Integer, nullable=False, default=0)  # 0 = not escalated, 1 = escalated
    escalation_reason = Column(String(100), nullable=True)  # low_confidence, angry_sentiment, complex_query, etc.
    escalated_to = Column(String(50), nullable=True)  # human_agent, supervisor, etc.
    escalation_timestamp = Column(DateTime, nullable=True)
    
    # Conversation metrics
    total_messages = Column(Integer, nullable=False, default=0)
    ai_responses = Column(Integer, nullable=False, default=0)
    user_messages = Column(Integer, nullable=False, default=0)
    
    # Context
    channel = Column(String(50), nullable=False)  # web, voice, email, chat
    language = Column(String(10), nullable=False)
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0
    
    # SLA
    escalation_rate_threshold = Column(Float, nullable=False, default=15.0)  # 15%
    threshold_violation = Column(Integer, nullable=False, default=0)  # 0 = no, 1 = yes
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<EscalationRate(id={self.id}, is_escalated={self.is_escalated}, reason={self.escalation_reason})>"
