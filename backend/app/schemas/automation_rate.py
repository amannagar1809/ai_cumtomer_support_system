"""Automation rate metrics schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AutomationRateRequest(BaseModel):
    """Request to record automation rate metrics."""

    conversation_id: UUID = Field(..., description="Conversation ID")
    user_id: UUID = Field(..., description="User ID")
    automation_type: str = Field(..., description="Automation type (fully_automated, hybrid, human_only)")
    total_messages: int = Field(default=0, description="Total messages")
    ai_messages: int = Field(default=0, description="AI messages")
    human_messages: int = Field(default=0, description="Human messages")
    conversation_duration_seconds: Optional[float] = Field(default=None, description="Conversation duration in seconds")
    intent_category: Optional[str] = Field(default=None, description="Intent category for target tracking")
    predicted_intent: Optional[str] = Field(default=None, description="Predicted intent")
    estimated_human_time_minutes: Optional[float] = Field(default=None, description="Estimated time if handled by human")
    actual_human_time_minutes: Optional[float] = Field(default=None, description="Actual human time spent")
    agent_cost_per_hour: float = Field(default=25.0, description="Agent cost per hour")
    channel: str = Field(..., description="Channel (web, voice, email, chat)")
    language: str = Field(..., description="Language")


class AutomationRateResponse(BaseModel):
    """Response for automation rate recording."""

    metrics_id: UUID = Field(..., description="Metrics ID")
    automation_type: str = Field(..., description="Automation type")
    cost_savings: Optional[float] = Field(default=None, description="Calculated cost savings")
    success: bool = Field(..., description="Whether recording was successful")
    message: str = Field(..., description="Status message")


class AutomationTypeBreakdown(BaseModel):
    """Breakdown by automation type."""

    automation_type: str = Field(..., description="Automation type (fully_automated, hybrid, human_only)")
    count: int = Field(..., description="Count of conversations")
    percentage: float = Field(..., description="Percentage of total conversations")


class AutomationRateSummary(BaseModel):
    """Summary of automation rate metrics."""

    period: str = Field(..., description="Time period (monthly)")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    total_conversations: int = Field(..., description="Total conversations")
    fully_automated: int = Field(..., description="Fully automated conversations")
    hybrid: int = Field(..., description="Hybrid conversations")
    human_only: int = Field(..., description="Human-only conversations")
    automation_rate: float = Field(..., description="Automation rate (percentage)")
    type_breakdown: list[AutomationTypeBreakdown] = Field(..., description="Breakdown by type")


class CostSavings(BaseModel):
    """Cost savings metrics."""

    period: str = Field(..., description="Time period (monthly)")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    total_hours_saved: float = Field(..., description="Total hours saved")
    total_cost_savings: float = Field(..., description="Total cost savings")
    avg_cost_per_conversation: float = Field(..., description="Average cost saved per conversation")
    agent_cost_per_hour: float = Field(..., description="Agent cost per hour used")


class IntentCategoryTarget(BaseModel):
    """Automation target by intent category."""

    intent_category: str = Field(..., description="Intent category")
    target_rate: float = Field(..., description="Target automation rate (percentage)")
    actual_rate: float = Field(..., description="Actual automation rate (percentage)")
    gap: float = Field(..., description="Gap between target and actual")
    total_conversations: int = Field(..., description="Total conversations in category")
    automated_conversations: int = Field(..., description="Automated conversations in category")


class AutomationRateAnalyticsResponse(BaseModel):
    """Complete automation rate analytics response."""

    monthly_summary: AutomationRateSummary = Field(..., description="Monthly summary")
    cost_savings: CostSavings = Field(..., description="Cost savings metrics")
    intent_category_targets: list[IntentCategoryTarget] = Field(..., description="Targets by intent category")
