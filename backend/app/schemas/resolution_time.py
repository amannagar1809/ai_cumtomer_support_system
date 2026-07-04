"""Resolution time metrics schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ResolutionTimeMetricsRequest(BaseModel):
    """Request to record resolution time metrics."""

    conversation_id: UUID = Field(..., description="Conversation ID")
    user_id: UUID = Field(..., description="User ID")
    conversation_started_at: datetime = Field(..., description="Conversation start time")
    first_message_at: datetime = Field(..., description="First message time")
    first_response_at: Optional[datetime] = Field(default=None, description="First response time")
    conversation_ended_at: Optional[datetime] = Field(default=None, description="Conversation end time")
    priority_level: str = Field(..., description="Priority level (low, medium, high, urgent)")
    channel: str = Field(..., description="Channel (web, voice, email, chat)")
    customer_tier: str = Field(..., description="Customer tier (regular, premium, vip)")


class ResolutionTimeMetricsResponse(BaseModel):
    """Response for resolution time metrics recording."""

    metrics_id: UUID = Field(..., description="Metrics ID")
    conversation_id: UUID = Field(..., description="Conversation ID")
    first_response_time_seconds: Optional[float] = Field(default=None, description="FRT in seconds")
    average_handle_time_seconds: Optional[float] = Field(default=None, description="AHT in seconds")
    sla_frt_violation: bool = Field(..., description="FRT SLA violation")
    sla_aht_violation: bool = Field(..., description="AHT SLA violation")
    success: bool = Field(..., description="Whether recording was successful")
    message: str = Field(..., description="Status message")


class ResolutionTimeSummary(BaseModel):
    """Summary of resolution time metrics."""

    period: str = Field(..., description="Time period (daily, weekly, monthly)")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    avg_frt_seconds: float = Field(..., description="Average First Response Time")
    avg_aht_seconds: float = Field(..., description="Average Handle Time")
    total_conversations: int = Field(..., description="Total conversations")
    frt_sla_compliance_rate: float = Field(..., description="FRT SLA compliance rate (0-1)")
    aht_sla_compliance_rate: float = Field(..., description="AHT SLA compliance rate (0-1)")


class ResolutionTimeBreakdown(BaseModel):
    """Breakdown of resolution time by dimension."""

    dimension: str = Field(..., description="Dimension (priority_level, channel, customer_tier)")
    value: str = Field(..., description="Dimension value")
    avg_frt_seconds: float = Field(..., description="Average FRT")
    avg_aht_seconds: float = Field(..., description="Average AHT")
    total_conversations: int = Field(..., description="Total conversations")
    frt_sla_compliance_rate: float = Field(..., description="FRT SLA compliance rate")
    aht_sla_compliance_rate: float = Field(..., description="AHT SLA compliance rate")


class SLAViolation(BaseModel):
    """SLA violation record."""

    violation_id: UUID = Field(..., description="Violation ID")
    conversation_id: UUID = Field(..., description="Conversation ID")
    violation_type: str = Field(..., description="Violation type (frt, aht)")
    actual_value_seconds: float = Field(..., description="Actual value in seconds")
    target_value_seconds: float = Field(..., description="Target value in seconds")
    priority_level: str = Field(..., description="Priority level")
    channel: str = Field(..., description="Channel")
    customer_tier: str = Field(..., description="Customer tier")
    occurred_at: datetime = Field(..., description="Violation time")


class ResolutionTimeAnalyticsResponse(BaseModel):
    """Complete resolution time analytics response."""

    daily_summary: ResolutionTimeSummary = Field(..., description="Daily summary")
    weekly_summary: ResolutionTimeSummary = Field(..., description="Weekly summary")
    monthly_summary: ResolutionTimeSummary = Field(..., description="Monthly summary")
    priority_breakdown: list[ResolutionTimeBreakdown] = Field(..., description="Breakdown by priority")
    channel_breakdown: list[ResolutionTimeBreakdown] = Field(..., description="Breakdown by channel")
    tier_breakdown: list[ResolutionTimeBreakdown] = Field(..., description="Breakdown by customer tier")
    sla_violations: list[SLAViolation] = Field(..., description="Recent SLA violations")
