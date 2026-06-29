"""Agent performance metrics models."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class AgentPerformance(Base):
    """Agent performance model for tracking agent metrics."""

    __tablename__ = "agent_performance"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    conversation_id = Column(PG_UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True)
    agent_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Ticket metrics
    tickets_closed = Column(Integer, nullable=False, default=0)
    average_handle_time_seconds = Column(Float, nullable=True)  # AHT
    
    # CSAT metrics
    csat_score = Column(Float, nullable=True)  # Average CSAT for this conversation
    csat_count = Column(Integer, nullable=False, default=0)  # Number of CSAT surveys
    
    # Utilization metrics
    active_time_seconds = Column(Float, nullable=True)  # Time spent on active tickets
    total_time_seconds = Column(Float, nullable=True)  # Total available time
    utilization_rate = Column(Float, nullable=True)  # Utilization rate (0-1)
    
    # Escalation metrics
    agent_escalated = Column(Integer, nullable=False, default=0)  # 0 = no, 1 = yes
    auto_escalated = Column(Integer, nullable=False, default=0)  # 0 = no, 1 = yes
    escalation_reason = Column(String(100), nullable=True)
    
    # AI comparison metrics
    ai_handled = Column(Integer, nullable=False, default=0)  # 0 = no, 1 = yes
    handoff_to_agent = Column(Integer, nullable=False, default=0)  # 0 = no, 1 = yes
    ai_vs_agent = Column(String(20), nullable=True)  # ai, agent, hybrid
    
    # Context
    channel = Column(String(50), nullable=False)  # web, voice, email, chat
    language = Column(String(10), nullable=False)
    
    # Period tracking
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AgentPerformance(id={self.id}, agent_id={self.agent_id}, tickets_closed={self.tickets_closed})>"
