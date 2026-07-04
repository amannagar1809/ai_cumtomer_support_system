"""Agent performance metrics service."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_performance import AgentPerformance
from app.schemas.agent_performance import (
    AIAgentComparison,
    AgentMetrics,
    AgentPerformanceAnalyticsResponse,
    EscalationRatio,
    WeeklyAgentReport,
)

logger = logging.getLogger(__name__)


class AgentPerformanceService:
    """Service for agent performance metrics."""

    def __init__(self, db: AsyncSession):
        """
        Initialize agent performance service.

        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger

    async def record_metrics(
        self,
        conversation_id: UUID,
        agent_id: UUID,
        tickets_closed: int,
        average_handle_time_seconds: Optional[float],
        csat_score: Optional[float],
        csat_count: int,
        active_time_seconds: Optional[float],
        total_time_seconds: Optional[float],
        agent_escalated: bool,
        auto_escalated: bool,
        escalation_reason: Optional[str],
        ai_handled: bool,
        handoff_to_agent: bool,
        ai_vs_agent: Optional[str],
        channel: str,
        language: str,
        period_start: datetime,
        period_end: datetime,
    ) -> AgentPerformance:
        """
        Record agent performance metrics for a conversation.

        Args:
            conversation_id: Conversation ID
            agent_id: Agent ID
            tickets_closed: Tickets closed
            average_handle_time_seconds: Average handle time in seconds
            csat_score: CSAT score
            csat_count: CSAT survey count
            active_time_seconds: Active time in seconds
            total_time_seconds: Total available time in seconds
            agent_escalated: Agent escalated
            auto_escalated: Auto escalated
            escalation_reason: Escalation reason
            ai_handled: AI handled
            handoff_to_agent: Handoff to agent
            ai_vs_agent: AI vs agent (ai, agent, hybrid)
            channel: Channel (web, voice, email, chat)
            language: Language
            period_start: Period start
            period_end: Period end

        Returns:
            Created agent performance metrics
        """
        # Calculate utilization rate
        utilization_rate = None
        if active_time_seconds and total_time_seconds and total_time_seconds > 0:
            utilization_rate = active_time_seconds / total_time_seconds

        # Convert booleans to integers
        agent_escalated_int = 1 if agent_escalated else 0
        auto_escalated_int = 1 if auto_escalated else 0
        ai_handled_int = 1 if ai_handled else 0
        handoff_to_agent_int = 1 if handoff_to_agent else 0

        # Create metrics record
        metrics = AgentPerformance(
            conversation_id=conversation_id,
            agent_id=agent_id,
            tickets_closed=tickets_closed,
            average_handle_time_seconds=average_handle_time_seconds,
            csat_score=csat_score,
            csat_count=csat_count,
            active_time_seconds=active_time_seconds,
            total_time_seconds=total_time_seconds,
            utilization_rate=utilization_rate,
            agent_escalated=agent_escalated_int,
            auto_escalated=auto_escalated_int,
            escalation_reason=escalation_reason,
            ai_handled=ai_handled_int,
            handoff_to_agent=handoff_to_agent_int,
            ai_vs_agent=ai_vs_agent,
            channel=channel,
            language=language,
            period_start=period_start,
            period_end=period_end,
        )

        self.db.add(metrics)
        await self.db.commit()
        await self.db.refresh(metrics)

        self.logger.info(
            f"Agent performance metrics recorded: agent_id={agent_id}, "
            f"tickets_closed={tickets_closed}, utilization={utilization_rate:.2f}"
        )

        return metrics

    async def calculate_agent_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[AgentMetrics]:
        """
        Calculate per-agent metrics.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of agent metrics
        """
        query = (
            select(
                AgentPerformance.agent_id.label("agent_id"),
                func.sum(AgentPerformance.tickets_closed).label("tickets_closed"),
                func.avg(AgentPerformance.average_handle_time_seconds).label("avg_aht"),
                func.avg(AgentPerformance.csat_score).label("avg_csat"),
                func.sum(AgentPerformance.csat_count).label("csat_count"),
                func.avg(AgentPerformance.utilization_rate).label("avg_utilization"),
            )
            .where(
                AgentPerformance.period_start >= start_date,
                AgentPerformance.period_end <= end_date,
            )
            .group_by(AgentPerformance.agent_id)
        )

        result = await self.db.execute(query)
        agent_metrics = []

        for row in result:
            agent_metrics.append(
                AgentMetrics(
                    agent_id=row.agent_id,
                    tickets_closed=int(row.tickets_closed or 0),
                    average_handle_time_seconds=float(row.avg_aht) if row.avg_aht else 0.0,
                    average_csat=float(row.avg_csat) if row.avg_csat else 0.0,
                    csat_count=int(row.csat_count or 0),
                    utilization_rate=float(row.avg_utilization) if row.avg_utilization else 0.0,
                )
            )

        return agent_metrics

    async def calculate_escalation_ratio(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> EscalationRatio:
        """
        Calculate agent-escalated vs auto-escalated ratio.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Escalation ratio metrics
        """
        query = (
            select(
                func.sum(AgentPerformance.agent_escalated).label("agent_escalated"),
                func.sum(AgentPerformance.auto_escalated).label("auto_escalated"),
                func.count(AgentPerformance.id).label("total"),
            )
            .where(
                AgentPerformance.period_start >= start_date,
                AgentPerformance.period_end <= end_date,
            )
        )

        result = await self.db.execute(query)
        row = result.one_or_none()

        if row and row.total > 0:
            agent_escalated_count = int(row.agent_escalated or 0)
            auto_escalated_count = int(row.auto_escalated or 0)
            total = int(row.total)
            agent_escalated_ratio = agent_escalated_count / total if total > 0 else 0.0
            auto_escalated_ratio = auto_escalated_count / total if total > 0 else 0.0
        else:
            agent_escalated_count = 0
            auto_escalated_count = 0
            agent_escalated_ratio = 0.0
            auto_escalated_ratio = 0.0

        return EscalationRatio(
            agent_escalated_count=agent_escalated_count,
            auto_escalated_count=auto_escalated_count,
            agent_escalated_ratio=agent_escalated_ratio,
            auto_escalated_ratio=auto_escalated_ratio,
        )

    async def calculate_ai_agent_comparison(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> AIAgentComparison:
        """
        Calculate AI vs agent performance comparison.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            AI vs agent comparison metrics
        """
        # Get counts by type
        query = (
            select(
                AgentPerformance.ai_vs_agent.label("type"),
                func.count(AgentPerformance.id).label("count"),
                func.avg(AgentPerformance.average_handle_time_seconds).label("avg_aht"),
                func.avg(AgentPerformance.csat_score).label("avg_csat"),
            )
            .where(
                and_(
                    AgentPerformance.period_start >= start_date,
                    AgentPerformance.period_end <= end_date,
                    AgentPerformance.ai_vs_agent.isnot(None),
                )
            )
            .group_by(AgentPerformance.ai_vs_agent)
        )

        result = await self.db.execute(query)
        type_data = {}

        for row in result:
            type_data[row.type] = {
                "count": int(row.count),
                "avg_aht": float(row.avg_aht) if row.avg_aht else 0.0,
                "avg_csat": float(row.avg_csat) if row.avg_csat else 0.0,
            }

        # Extract metrics
        ai_data = type_data.get("ai", {"count": 0, "avg_aht": 0.0, "avg_csat": 0.0})
        agent_data = type_data.get("agent", {"count": 0, "avg_aht": 0.0, "avg_csat": 0.0})
        hybrid_data = type_data.get("hybrid", {"count": 0, "avg_aht": 0.0, "avg_csat": 0.0})

        return AIAgentComparison(
            ai_handled_count=ai_data["count"],
            agent_handled_count=agent_data["count"],
            hybrid_count=hybrid_data["count"],
            ai_avg_handle_time=ai_data["avg_aht"],
            agent_avg_handle_time=agent_data["avg_aht"],
            ai_avg_csat=ai_data["avg_csat"],
            agent_avg_csat=agent_data["avg_csat"],
        )

    async def generate_weekly_reports(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[WeeklyAgentReport]:
        """
        Generate weekly agent performance reports.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of weekly agent reports
        """
        # Group by agent and week
        query = (
            select(
                AgentPerformance.agent_id.label("agent_id"),
                func.date_trunc("week", AgentPerformance.period_start).label("week_start"),
                func.date_trunc("week", AgentPerformance.period_end).label("week_end"),
                func.sum(AgentPerformance.tickets_closed).label("tickets_closed"),
                func.avg(AgentPerformance.average_handle_time_seconds).label("avg_aht"),
                func.avg(AgentPerformance.csat_score).label("avg_csat"),
                func.avg(AgentPerformance.utilization_rate).label("avg_utilization"),
                func.sum(AgentPerformance.agent_escalated).label("agent_escalated"),
                func.sum(AgentPerformance.auto_escalated).label("auto_escalated"),
            )
            .where(
                AgentPerformance.period_start >= start_date,
                AgentPerformance.period_end <= end_date,
            )
            .group_by(
                AgentPerformance.agent_id,
                func.date_trunc("week", AgentPerformance.period_start),
                func.date_trunc("week", AgentPerformance.period_end),
            )
            .order_by(AgentPerformance.agent_id, func.date_trunc("week", AgentPerformance.period_start))
        )

        result = await self.db.execute(query)
        weekly_reports = []

        for row in result:
            weekly_reports.append(
                WeeklyAgentReport(
                    agent_id=row.agent_id,
                    week_start=row.week_start,
                    week_end=row.week_end,
                    tickets_closed=int(row.tickets_closed or 0),
                    average_handle_time_seconds=float(row.avg_aht) if row.avg_aht else 0.0,
                    average_csat=float(row.avg_csat) if row.avg_csat else 0.0,
                    utilization_rate=float(row.avg_utilization) if row.avg_utilization else 0.0,
                    agent_escalated_count=int(row.agent_escalated or 0),
                    auto_escalated_count=int(row.auto_escalated or 0),
                )
            )

        return weekly_reports

    async def get_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> AgentPerformanceAnalyticsResponse:
        """
        Get complete agent performance analytics.

        Args:
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: now)

        Returns:
            Complete agent performance analytics
        """
        # Set default dates
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Calculate agent metrics
        agent_metrics = await self.calculate_agent_metrics(start_date, end_date)

        # Calculate escalation ratio
        escalation_ratio = await self.calculate_escalation_ratio(start_date, end_date)

        # Calculate AI vs agent comparison
        ai_agent_comparison = await self.calculate_ai_agent_comparison(start_date, end_date)

        # Generate weekly reports
        weekly_reports = await self.generate_weekly_reports(start_date, end_date)

        return AgentPerformanceAnalyticsResponse(
            period_start=start_date,
            period_end=end_date,
            agent_metrics=agent_metrics,
            escalation_ratio=escalation_ratio,
            ai_agent_comparison=ai_agent_comparison,
            weekly_reports=weekly_reports,
        )
