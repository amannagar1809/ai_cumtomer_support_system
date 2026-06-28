"""Escalation rate metrics schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EscalationRateRequest(BaseModel):
    """Request to record escalation rate metrics."""

    conversation_id: UUID = Field(..., description="Conversation ID")
    user_id: UUID = Field(..., description="User ID")
    is_escalated: bool = Field(..., description="Whether conversation was escalated")
    escalation_reason: Optional[str] = Field(default=None, description="Escalation reason")
    escalated_to: Optional[str] = Field(default=None, description="Escalated to (human_agent, supervisor)")
    escalation_timestamp: Optional[datetime] = Field(default=None, description="Escalation timestamp")
    total_messages: int = Field(default=0, description="Total messages")
    ai_responses: int = Field(default=0, description="AI responses")
    user_messages: int = Field(default=0, description="User messages")
    channel: str = Field(..., description="Channel (web, voice, email, chat)")
    language: str = Field(..., description="Language")
    sentiment_score: Optional[float] = Field(default=None, description="Sentiment score (-1.0 to 1.0)")
    confidence_score: Optional[float] = Field(default=None, description="Confidence score (0.0 to 1.0)")


class EscalationRateResponse(BaseModel):
    """Response for escalation rate recording."""

    metrics_id: UUID = Field(..., description="Metrics ID")
    is_escalated: bool = Field(..., description="Whether conversation was escalated")
    escalation_rate_threshold: float = Field(..., description="Escalation rate threshold")
    threshold_violation: bool = Field(..., description="Threshold violation")
    success: bool = Field(..., description="Whether recording was successful")
    message: str = Field(..., description="Status message")


class EscalationRateSummary(BaseModel):
    """Summary of escalation rate metrics."""

    period: str = Field(..., description="Time period (daily, weekly, monthly)")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    total_conversations: int = Field(..., description="Total conversations")
    escalated_conversations: int = Field(..., description="Escalated conversations")
    escalation_rate: float = Field(..., description="Escalation rate (percentage)")
    threshold: float = Field(..., description="Escalation rate threshold")
    threshold_violation: bool = Field(..., description="Threshold violation")


class EscalationReasonBreakdown(BaseModel):
    """Breakdown by escalation reason."""

    escalation_reason: str = Field(..., description="Escalation reason")
    count: int = Field(..., description="Count of escalations")
    percentage: float = Field(..., description="Percentage of total escalations")


class EscalationTrendPoint(BaseModel):
    """A point in the escalation trend."""

    date: datetime = Field(..., description="Date")
    total_conversations: int = Field(..., description="Total conversations")
    escalated_conversations: int = Field(..., description="Escalated conversations")
    escalation_rate: float = Field(..., description="Escalation rate (percentage)")


class EscalationTrend(BaseModel):
    """Escalation trend over time."""

    period: str = Field(..., description="Period (daily, weekly, monthly)")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    trend_points: list[EscalationTrendPoint] = Field(..., description="Trend data points")
    overall_trend: str = Field(default="stable", description="Overall trend (increasing, decreasing, stable)")
    average_rate: float = Field(..., description="Average escalation rate")


class EscalationAlert(BaseModel):
    """Escalation rate alert."""

    alert_id: UUID = Field(..., description="Alert ID")
    alert_type: str = Field(default="escalation_rate_high", description="Alert type")
    threshold: float = Field(default=15.0, description="Alert threshold (percentage)")
    current_rate: float = Field(..., description="Current escalation rate")
    period: str = Field(..., description="Time period")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    triggered_at: datetime = Field(..., description="Alert triggered time")
    acknowledged: bool = Field(default=False, description="Whether alert was acknowledged")
    acknowledged_at: Optional[datetime] = Field(default=None, description="Acknowledgment time")
    acknowledged_by: Optional[UUID] = Field(default=None, description="User who acknowledged")


class EscalationRateAnalyticsResponse(BaseModel):
    """Complete escalation rate analytics response."""

    daily_summary: EscalationRateSummary = Field(..., description="Daily summary")
    weekly_summary: EscalationRateSummary = Field(..., description="Weekly summary")
    monthly_summary: EscalationRateSummary = Field(..., description="Monthly summary")
    reason_breakdown: list[EscalationReasonBreakdown] = Field(..., description="Breakdown by escalation reason")
    trend: EscalationTrend = Field(..., description="Trend over time")
    alerts: list[EscalationAlert] = Field(default_factory=list, description="Active alerts")
