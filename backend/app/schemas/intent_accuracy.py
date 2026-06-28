"""Intent accuracy metrics schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class IntentAccuracyRecord(BaseModel):
    """Intent accuracy record."""

    id: UUID = Field(..., description="Record ID")
    conversation_id: UUID = Field(..., description="Conversation ID")
    user_message: str = Field(..., description="User message")
    predicted_intent: str = Field(..., description="Predicted intent")
    actual_intent: str = Field(..., description="Actual intent (from review)")
    is_correct: bool = Field(..., description="Whether prediction was correct")
    predicted_confidence: float = Field(..., description="Predicted confidence score")
    language: str = Field(..., description="Language")
    model_variant: Optional[str] = Field(default=None, description="Model variant")
    classification_id: Optional[str] = Field(default=None, description="Classification ID")
    reviewed_at: Optional[datetime] = Field(default=None, description="Review timestamp")


class IntentAccuracyRequest(BaseModel):
    """Request to record intent accuracy."""

    conversation_id: UUID = Field(..., description="Conversation ID")
    user_id: UUID = Field(..., description="User ID")
    user_message: str = Field(..., description="User message")
    predicted_intent: str = Field(..., description="Predicted intent")
    actual_intent: str = Field(..., description="Actual intent (from review)")
    predicted_confidence: float = Field(..., ge=0.0, le=1.0, description="Predicted confidence score")
    confidence_distribution: Optional[dict] = Field(default=None, description="Confidence distribution")
    language: str = Field(..., description="Language")
    model_variant: Optional[str] = Field(default=None, description="Model variant")
    classification_id: Optional[str] = Field(default=None, description="Classification ID")
    review_notes: Optional[str] = Field(default=None, description="Review notes")


class IntentAccuracyResponse(BaseModel):
    """Response for intent accuracy recording."""

    record_id: UUID = Field(..., description="Record ID")
    is_correct: bool = Field(..., description="Whether prediction was correct")
    success: bool = Field(..., description="Whether recording was successful")
    message: str = Field(..., description="Status message")


class IntentClassAccuracy(BaseModel):
    """Accuracy metrics for an intent class."""

    intent_class: str = Field(..., description="Intent class name")
    total_predictions: int = Field(..., description="Total predictions")
    correct_predictions: int = Field(..., description="Correct predictions")
    accuracy: float = Field(..., description="Accuracy (0-1)")
    avg_confidence: float = Field(..., description="Average confidence score")


class MisclassifiedQuery(BaseModel):
    """A misclassified query example."""

    id: UUID = Field(..., description="Record ID")
    user_message: str = Field(..., description="User message")
    predicted_intent: str = Field(..., description="Predicted intent")
    actual_intent: str = Field(..., description="Actual intent")
    predicted_confidence: float = Field(..., description="Predicted confidence")
    language: str = Field(..., description="Language")
    occurred_at: datetime = Field(..., description="Timestamp")


class ConfidenceDistribution(BaseModel):
    """Confidence score distribution."""

    range_0_20: int = Field(..., description="Count in 0.0-0.2 range")
    range_20_40: int = Field(..., description="Count in 0.2-0.4 range")
    range_40_60: int = Field(..., description="Count in 0.4-0.6 range")
    range_60_80: int = Field(..., description="Count in 0.6-0.8 range")
    range_80_100: int = Field(..., description="Count in 0.8-1.0 range")
    avg_confidence: float = Field(..., description="Average confidence")
    median_confidence: float = Field(..., description="Median confidence")


class ConfusionMatrixCell(BaseModel):
    """A cell in the confusion matrix."""

    predicted_intent: str = Field(..., description="Predicted intent")
    actual_intent: str = Field(..., description="Actual intent")
    count: int = Field(..., description="Count of occurrences")


class IntentAccuracyAnalyticsResponse(BaseModel):
    """Complete intent accuracy analytics response."""

    overall_accuracy: float = Field(..., description="Overall accuracy (0-1)")
    total_predictions: int = Field(..., description="Total predictions")
    intent_class_accuracy: list[IntentClassAccuracy] = Field(..., description="Accuracy per intent class")
    misclassified_queries: list[MisclassifiedQuery] = Field(..., description="Frequently misclassified queries")
    confidence_distribution: ConfidenceDistribution = Field(..., description="Confidence score distribution")
    confusion_matrix: list[ConfusionMatrixCell] = Field(..., description="Confusion matrix")
