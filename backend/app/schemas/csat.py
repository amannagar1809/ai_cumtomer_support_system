"""CSAT (Customer Satisfaction) schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CSATSurveyRequest(BaseModel):
    """Request to submit CSAT survey."""

    conversation_id: UUID = Field(..., description="Conversation ID")
    user_id: UUID = Field(..., description="User ID")
    score: int = Field(..., ge=1, le=5, description="CSAT score (1-5)")
    feedback: Optional[str] = Field(default=None, description="Optional text feedback")
    channel: str = Field(..., description="Channel (web, voice, email, chat)")
    language: str = Field(..., description="Language (en, hi, etc.)")
    agent_type: str = Field(..., description="Agent type (ai, human)")
    agent_id: Optional[UUID] = Field(default=None, description="Agent ID if human")


class CSATSurveyResponse(BaseModel):
    """Response for CSAT survey submission."""

    survey_id: UUID = Field(..., description="Survey ID")
    conversation_id: UUID = Field(..., description="Conversation ID")
    score: int = Field(..., description="CSAT score")
    feedback: Optional[str] = Field(default=None, description="Feedback text")
    channel: str = Field(..., description="Channel")
    language: str = Field(..., description="Language")
    agent_type: str = Field(..., description="Agent type")
    agent_id: Optional[UUID] = Field(default=None, description="Agent ID")
    survey_completed_at: datetime = Field(..., description="Survey completion time")
    success: bool = Field(..., description="Whether submission was successful")
    message: str = Field(..., description="Status message")


class CSATMetrics(BaseModel):
    """CSAT metrics for a time period."""

    period: str = Field(..., description="Time period (daily, weekly, monthly)")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    average_score: float = Field(..., description="Average CSAT score")
    total_surveys: int = Field(..., description="Total number of surveys")
    score_distribution: dict[int, int] = Field(default_factory=dict, description="Distribution of scores (1-5)")


class CSATBreakdown(BaseModel):
    """CSAT breakdown by dimension."""

    dimension: str = Field(..., description="Dimension (channel, language, agent_type)")
    value: str = Field(..., description="Dimension value")
    average_score: float = Field(..., description="Average CSAT score")
    total_surveys: int = Field(..., description="Total surveys")
    trend: str = Field(default="stable", description="Trend (up, down, stable)")


class CSATTrendPoint(BaseModel):
    """A point in the CSAT trend line."""

    date: datetime = Field(..., description="Date")
    average_score: float = Field(..., description="Average CSAT score")
    total_surveys: int = Field(..., description="Total surveys")


class CSATTrend(BaseModel):
    """CSAT trend over time."""

    period: str = Field(..., description="Period (daily, weekly, monthly)")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    trend_points: list[CSATTrendPoint] = Field(..., description="Trend data points")
    overall_trend: str = Field(default="stable", description="Overall trend (up, down, stable)")
    average_score: float = Field(..., description="Average score over period")


class CSATAlert(BaseModel):
    """CSAT alert for low scores."""

    alert_id: UUID = Field(..., description="Alert ID")
    alert_type: str = Field(default="csat_drop", description="Alert type")
    threshold: float = Field(default=4.0, description="Alert threshold")
    current_score: float = Field(..., description="Current CSAT score")
    period: str = Field(..., description="Time period")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    triggered_at: datetime = Field(..., description="Alert triggered time")
    acknowledged: bool = Field(default=False, description="Whether alert was acknowledged")
    acknowledged_at: Optional[datetime] = Field(default=None, description="Acknowledgment time")
    acknowledged_by: Optional[UUID] = Field(default=None, description="User who acknowledged")


class CSATAnalyticsResponse(BaseModel):
    """Complete CSAT analytics response."""

    daily_metrics: CSATMetrics = Field(..., description="Daily metrics")
    weekly_metrics: CSATMetrics = Field(..., description="Weekly metrics")
    monthly_metrics: CSATMetrics = Field(..., description="Monthly metrics")
    channel_breakdown: list[CSATBreakdown] = Field(..., description="Breakdown by channel")
    language_breakdown: list[CSATBreakdown] = Field(..., description="Breakdown by language")
    agent_breakdown: list[CSATBreakdown] = Field(..., description="Breakdown by agent type")
    trend: CSATTrend = Field(..., description="Trend over time")
    alerts: list[CSATAlert] = Field(default_factory=list, description="Active alerts")
