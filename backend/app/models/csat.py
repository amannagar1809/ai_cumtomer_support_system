"""CSAT (Customer Satisfaction) models."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class CSATSurvey(Base):
    """CSAT survey model."""

    __tablename__ = "csat_surveys"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    conversation_id = Column(PG_UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    score = Column(Integer, nullable=False)  # 1-5 scale
    feedback = Column(Text, nullable=True)  # Optional text feedback
    channel = Column(String(50), nullable=False)  # web, voice, email, chat
    language = Column(String(10), nullable=False)  # en, hi, etc.
    agent_type = Column(String(20), nullable=False)  # ai, human
    agent_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Agent ID if human
    survey_sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    survey_completed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CSATSurvey(id={self.id}, conversation_id={self.conversation_id}, score={self.score})>"
