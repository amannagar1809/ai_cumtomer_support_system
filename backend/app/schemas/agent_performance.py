"""Agent performance metrics schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AgentPerformanceRequest(BaseModel):
    """Request to record agent performance metrics."""

    conversation_id: UUID = Field(..., description="Conversation ID")
    agent_id: UUID = Field(..., description="Agent ID")
    tickets_closed: int = Field(default=0, description="Tickets closed")
    average_handle_time_seconds: Optional[float] = Field(default=None, description="Average handle time in seconds")
    csat_score: Optional[float] = Field(default=None, description="CSAT score")
    csat_count: int = Field(default=0, description="CSAT survey count")
    active_time_seconds: Optional[float] = Field(default=None, description="Active time in seconds")
    total_time_seconds: Optional[float] = Field(default=None, description="Total available time in seconds")
    agent_escalated: bool = Field(default=False, description="Agent escalated")
    auto_escalated: bool = Field(default=False, description="Auto escalated")
    escalation_reason: Optional[str] = Field(default=None, description="Escalation reason")
    ai_handled: bool = Field(default=False, description="AI handled")
    handoff_to_agent: bool = Field(default=False, description="Handoff to agent")
    ai_vs_agent: Optional[str] = Field(default=None, description="AI vs agent (ai, agent, hybrid)")
    channel: str = Field(..., description="Channel (web, voice, email, chat)")
    language: str = Field(..., description="Language")
    period_start: datetime = Field(..., description="Period start")
    period_end: datetime = Field(..., description="Period end")


class AgentPerformanceResponse(BaseModel):
    """Response for agent performance recording."""

    metrics_id: UUID = Field(..., description="Metrics ID")
    utilization_rate: Optional[float] = Field(default=None, description="Calculated utilization rate")
    success: bool = Field(..., description="Whether recording was successful")
    message: str = Field(..., description="Status message")


class AgentMetrics(BaseModel):
    """Per-agent metrics."""

    agent_id: UUID = Field(..., description="Agent ID")
    tickets_closed: int = Field(..., description="Tickets closed")
    average_handle_time_seconds: float = Field(..., description="Average handle time")
    average_csat: float = Field(..., description="Average CSAT")
    csat_count: int = Field(..., description="CSAT survey count")
    utilization_rate: float = Field(..., description="Utilization rate (0-1)")


class EscalationRatio(BaseModel):
    """Escalation ratio metrics."""

    agent_escalated_count: int = Field(..., description="Agent escalated count")
    auto_escalated_count: int = Field(..., description="Auto escalated count")
    agent_escalated_ratio: float = Field(..., description="Agent escalated ratio")
    auto_escalated_ratio: float = Field(..., description="Auto escalated ratio")


class AIAgentComparison(BaseModel):
    """AI vs agent performance comparison."""

    ai_handled_count: int = Field(..., description="AI handled count")
    agent_handled_count: int = Field(..., description="Agent handled count")
    hybrid_count: int = Field(..., description="Hybrid count")
    ai_avg_handle_time: float = Field(..., description="AI average handle time")
    agent_avg_handle_time: float = Field(..., description="Agent average handle time")
    ai_avg_csat: float = Field(..., description="AI average CSAT")
    agent_avg_csat: float = Field(..., description="Agent average CSAT")


class WeeklyAgentReport(BaseModel):
    """Weekly agent performance report."""

    agent_id: UUID = Field(..., description="Agent ID")
    week_start: datetime = Field(..., description="Week start")
    week_end: datetime = Field(..., description="Week end")
    tickets_closed: int = Field(..., description="Tickets closed")
    average_handle_time_seconds: float = Field(..., description="Average handle time")
    average_csat: float = Field(..., description="Average CSAT")
    utilization_rate: float = Field(..., description="Utilization rate")
    agent_escalated_count: int = Field(..., description="Agent escalated count")
    auto_escalated_count: int = Field(..., description="Auto escalated count")


class AgentPerformanceAnalyticsResponse(BaseModel):
    """Complete agent performance analytics response."""

    period_start: datetime = Field(..., description="Period start")
    period_end: datetime = Field(..., description="Period end")
    agent_metrics: list[AgentMetrics] = Field(..., description="Per-agent metrics")
    escalation_ratio: EscalationRatio = Field(..., description="Escalation ratio")
    ai_agent_comparison: AIAgentComparison = Field(..., description="AI vs agent comparison")
    weekly_reports: list[WeeklyAgentReport] = Field(..., description="Weekly agent reports")
