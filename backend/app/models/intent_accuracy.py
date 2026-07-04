"""Intent accuracy metrics models."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class IntentAccuracy(Base):
    """Intent accuracy model for tracking predicted vs actual intent."""

    __tablename__ = "intent_accuracy"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    conversation_id = Column(PG_UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Intent data
    user_message = Column(Text, nullable=False)
    predicted_intent = Column(String(100), nullable=False)
    actual_intent = Column(String(100), nullable=False)
    is_correct = Column(Integer, nullable=False, default=0)  # 0 = incorrect, 1 = correct
    
    # Confidence scores
    predicted_confidence = Column(Float, nullable=False)
    confidence_distribution = Column(String(500), nullable=True)  # JSON string of confidence distribution
    
    # Metadata
    language = Column(String(10), nullable=False)
    model_variant = Column(String(50), nullable=True)  # A/B test model variant
    classification_id = Column(String(100), nullable=True)  # Unique classification ID
    
    # Review
    reviewed_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<IntentAccuracy(id={self.id}, predicted={self.predicted_intent}, actual={self.actual_intent}, correct={self.is_correct})>"
