"""Resolution time metrics models."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class ResolutionTimeMetrics(Base):
    """Resolution time metrics model."""

    __tablename__ = "resolution_time_metrics"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    conversation_id = Column(PG_UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Timestamps
    conversation_started_at = Column(DateTime, nullable=False)
    first_message_at = Column(DateTime, nullable=False)
    first_response_at = Column(DateTime, nullable=True)
    conversation_ended_at = Column(DateTime, nullable=True)
    
    # Metrics
    first_response_time_seconds = Column(Float, nullable=True)  # FRT in seconds
    average_handle_time_seconds = Column(Float, nullable=True)  # AHT in seconds
    
    # Dimensions
    priority_level = Column(String(20), nullable=False)  # low, medium, high, urgent
    channel = Column(String(50), nullable=False)  # web, voice, email, chat
    customer_tier = Column(String(20), nullable=False)  # regular, premium, vip
    
    # SLA
    sla_frt_target_seconds = Column(Float, nullable=False, default=30.0)  # 30 seconds
    sla_aht_target_seconds = Column(Float, nullable=False, default=180.0)  # 3 minutes
    sla_frt_violation = Column(Integer, nullable=False, default=0)  # 0 = no, 1 = yes
    sla_aht_violation = Column(Integer, nullable=False, default=0)  # 0 = no, 1 = yes
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ResolutionTimeMetrics(id={self.id}, conversation_id={self.conversation_id}, frt={self.first_response_time_seconds})>"
