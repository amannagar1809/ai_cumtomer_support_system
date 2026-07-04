"""Resolution time metrics service."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resolution_time import ResolutionTimeMetrics
from app.schemas.resolution_time import (
    ResolutionTimeAnalyticsResponse,
    ResolutionTimeBreakdown,
    ResolutionTimeSummary,
    SLAViolation,
)

logger = logging.getLogger(__name__)

# SLA targets
SLA_FRT_TARGET_SECONDS = 30.0  # 30 seconds
SLA_AHT_TARGET_SECONDS = 180.0  # 3 minutes


class ResolutionTimeService:
    """Service for resolution time metrics."""

    def __init__(self, db: AsyncSession):
        """
        Initialize resolution time service.

        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger

    async def record_metrics(
        self,
        conversation_id: UUID,
        user_id: UUID,
        conversation_started_at: datetime,
        first_message_at: datetime,
        first_response_at: Optional[datetime],
        conversation_ended_at: Optional[datetime],
        priority_level: str,
        channel: str,
        customer_tier: str,
    ) -> ResolutionTimeMetrics:
        """
        Record resolution time metrics for a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            conversation_started_at: Conversation start time
            first_message_at: First message time
            first_response_at: First response time
            conversation_ended_at: Conversation end time
            priority_level: Priority level (low, medium, high, urgent)
            channel: Channel (web, voice, email, chat)
            customer_tier: Customer tier (regular, premium, vip)

        Returns:
            Created resolution time metrics
        """
        # Calculate First Response Time (FRT)
        first_response_time_seconds = None
        if first_response_at and first_message_at:
            first_response_time_seconds = (first_response_at - first_message_at).total_seconds()

        # Calculate Average Handle Time (AHT)
        average_handle_time_seconds = None
        if conversation_ended_at and conversation_started_at:
            average_handle_time_seconds = (conversation_ended_at - conversation_started_at).total_seconds()

        # Check SLA violations
        sla_frt_violation = 0
        if first_response_time_seconds and first_response_time_seconds > SLA_FRT_TARGET_SECONDS:
            sla_frt_violation = 1
            self.logger.warning(
                f"FRT SLA violation: conversation_id={conversation_id}, "
                f"frt={first_response_time_seconds:.2f}s, target={SLA_FRT_TARGET_SECONDS}s"
            )

        sla_aht_violation = 0
        if average_handle_time_seconds and average_handle_time_seconds > SLA_AHT_TARGET_SECONDS:
            sla_aht_violation = 1
            self.logger.warning(
                f"AHT SLA violation: conversation_id={conversation_id}, "
                f"aht={average_handle_time_seconds:.2f}s, target={SLA_AHT_TARGET_SECONDS}s"
            )

        # Create metrics record
        metrics = ResolutionTimeMetrics(
            conversation_id=conversation_id,
            user_id=user_id,
            conversation_started_at=conversation_started_at,
            first_message_at=first_message_at,
            first_response_at=first_response_at,
            conversation_ended_at=conversation_ended_at,
            first_response_time_seconds=first_response_time_seconds,
            average_handle_time_seconds=average_handle_time_seconds,
            priority_level=priority_level,
            channel=channel,
            customer_tier=customer_tier,
            sla_frt_target_seconds=SLA_FRT_TARGET_SECONDS,
            sla_aht_target_seconds=SLA_AHT_TARGET_SECONDS,
            sla_frt_violation=sla_frt_violation,
            sla_aht_violation=sla_aht_violation,
        )

        self.db.add(metrics)
        await self.db.commit()
        await self.db.refresh(metrics)

        self.logger.info(
            f"Resolution time metrics recorded: conversation_id={conversation_id}, "
            f"frt={first_response_time_seconds:.2f}s, aht={average_handle_time_seconds:.2f}s"
        )

        return metrics

    async def calculate_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        period: str,
    ) -> ResolutionTimeSummary:
        """
        Calculate resolution time summary for a time period.

        Args:
            start_date: Start date
            end_date: End date
            period: Period label (daily, weekly, monthly)

        Returns:
            Resolution time summary
        """
        query = (
            select(
                func.avg(ResolutionTimeMetrics.first_response_time_seconds).label("avg_frt"),
                func.avg(ResolutionTimeMetrics.average_handle_time_seconds).label("avg_aht"),
                func.count(ResolutionTimeMetrics.id).label("total_conversations"),
                func.sum(
                    func.case(
                        (ResolutionTimeMetrics.sla_frt_violation == 0, 1),
                        else_=0,
                    )
                ).label("frt_compliant"),
                func.sum(
                    func.case(
                        (ResolutionTimeMetrics.sla_aht_violation == 0, 1),
                        else_=0,
                    )
                ).label("aht_compliant"),
            )
            .where(
                ResolutionTimeMetrics.created_at >= start_date,
                ResolutionTimeMetrics.created_at <= end_date,
            )
        )

        result = await self.db.execute(query)
        row = result.one_or_none()

        if row and row.total_conversations > 0:
            avg_frt = float(row.avg_frt) if row.avg_frt else 0.0
            avg_aht = float(row.avg_aht) if row.avg_aht else 0.0
            total_conversations = int(row.total_conversations)
            frt_compliance_rate = float(row.frt_compliant) / total_conversations
            aht_compliance_rate = float(row.aht_compliant) / total_conversations
        else:
            avg_frt = 0.0
            avg_aht = 0.0
            total_conversations = 0
            frt_compliance_rate = 0.0
            aht_compliance_rate = 0.0

        return ResolutionTimeSummary(
            period=period,
            start_date=start_date,
            end_date=end_date,
            avg_frt_seconds=avg_frt,
            avg_aht_seconds=avg_aht,
            total_conversations=total_conversations,
            frt_sla_compliance_rate=frt_compliance_rate,
            aht_sla_compliance_rate=aht_compliance_rate,
        )

    async def calculate_breakdown(
        self,
        start_date: datetime,
        end_date: datetime,
        dimension: str,
    ) -> list[ResolutionTimeBreakdown]:
        """
        Calculate resolution time breakdown by dimension.

        Args:
            start_date: Start date
            end_date: End date
            dimension: Dimension (priority_level, channel, customer_tier)

        Returns:
            List of breakdowns
        """
        # Map dimension to column
        dimension_column = {
            "priority_level": ResolutionTimeMetrics.priority_level,
            "channel": ResolutionTimeMetrics.channel,
            "customer_tier": ResolutionTimeMetrics.customer_tier,
        }.get(dimension)

        if not dimension_column:
            raise ValueError(f"Invalid dimension: {dimension}")

        query = (
            select(
                dimension_column.label("dimension_value"),
                func.avg(ResolutionTimeMetrics.first_response_time_seconds).label("avg_frt"),
                func.avg(ResolutionTimeMetrics.average_handle_time_seconds).label("avg_aht"),
                func.count(ResolutionTimeMetrics.id).label("total_conversations"),
                func.sum(
                    func.case(
                        (ResolutionTimeMetrics.sla_frt_violation == 0, 1),
                        else_=0,
                    )
                ).label("frt_compliant"),
                func.sum(
                    func.case(
                        (ResolutionTimeMetrics.sla_aht_violation == 0, 1),
                        else_=0,
                    )
                ).label("aht_compliant"),
            )
            .where(
                ResolutionTimeMetrics.created_at >= start_date,
                ResolutionTimeMetrics.created_at <= end_date,
            )
            .group_by(dimension_column)
        )

        result = await self.db.execute(query)
        breakdowns = []

        for row in result:
            total = int(row.total_conversations)
            frt_compliance = float(row.frt_compliant) / total if total > 0 else 0.0
            aht_compliance = float(row.aht_compliant) / total if total > 0 else 0.0

            breakdowns.append(
                ResolutionTimeBreakdown(
                    dimension=dimension,
                    value=str(row.dimension_value),
                    avg_frt_seconds=float(row.avg_frt) if row.avg_frt else 0.0,
                    avg_aht_seconds=float(row.avg_aht) if row.avg_aht else 0.0,
                    total_conversations=total,
                    frt_sla_compliance_rate=frt_compliance,
                    aht_sla_compliance_rate=aht_compliance,
                )
            )

        return breakdowns

    async def get_sla_violations(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 50,
    ) -> list[SLAViolation]:
        """
        Get recent SLA violations.

        Args:
            start_date: Start date
            end_date: End date
            limit: Maximum number of violations to return

        Returns:
            List of SLA violations
        """
        violations = []

        # Get FRT violations
        frt_query = (
            select(ResolutionTimeMetrics)
            .where(
                and_(
                    ResolutionTimeMetrics.created_at >= start_date,
                    ResolutionTimeMetrics.created_at <= end_date,
                    ResolutionTimeMetrics.sla_frt_violation == 1,
                )
            )
            .order_by(ResolutionTimeMetrics.created_at.desc())
            .limit(limit)
        )

        frt_result = await self.db.execute(frt_query)
        for row in frt_result:
            violations.append(
                SLAViolation(
                    violation_id=row.id,
                    conversation_id=row.conversation_id,
                    violation_type="frt",
                    actual_value_seconds=row.first_response_time_seconds or 0.0,
                    target_value_seconds=row.sla_frt_target_seconds,
                    priority_level=row.priority_level,
                    channel=row.channel,
                    customer_tier=row.customer_tier,
                    occurred_at=row.created_at,
                )
            )

        # Get AHT violations
        aht_query = (
            select(ResolutionTimeMetrics)
            .where(
                and_(
                    ResolutionTimeMetrics.created_at >= start_date,
                    ResolutionTimeMetrics.created_at <= end_date,
                    ResolutionTimeMetrics.sla_aht_violation == 1,
                )
            )
            .order_by(ResolutionTimeMetrics.created_at.desc())
            .limit(limit)
        )

        aht_result = await self.db.execute(aht_query)
        for row in aht_result:
            violations.append(
                SLAViolation(
                    violation_id=row.id,
                    conversation_id=row.conversation_id,
                    violation_type="aht",
                    actual_value_seconds=row.average_handle_time_seconds or 0.0,
                    target_value_seconds=row.sla_aht_target_seconds,
                    priority_level=row.priority_level,
                    channel=row.channel,
                    customer_tier=row.customer_tier,
                    occurred_at=row.created_at,
                )
            )

        # Sort by occurred_at
        violations.sort(key=lambda x: x.occurred_at, reverse=True)

        return violations[:limit]

    async def get_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ResolutionTimeAnalyticsResponse:
        """
        Get complete resolution time analytics.

        Args:
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: now)

        Returns:
            Complete resolution time analytics
        """
        # Set default dates
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Calculate summaries
        daily_summary = await self.calculate_summary(
            start_date=end_date - timedelta(days=1),
            end_date=end_date,
            period="daily",
        )

        weekly_summary = await self.calculate_summary(
            start_date=end_date - timedelta(weeks=1),
            end_date=end_date,
            period="weekly",
        )

        monthly_summary = await self.calculate_summary(
            start_date=end_date - timedelta(days=30),
            end_date=end_date,
            period="monthly",
        )

        # Calculate breakdowns
        priority_breakdown = await self.calculate_breakdown(start_date, end_date, "priority_level")
        channel_breakdown = await self.calculate_breakdown(start_date, end_date, "channel")
        tier_breakdown = await self.calculate_breakdown(start_date, end_date, "customer_tier")

        # Get SLA violations
        sla_violations = await self.get_sla_violations(start_date, end_date)

        return ResolutionTimeAnalyticsResponse(
            daily_summary=daily_summary,
            weekly_summary=weekly_summary,
            monthly_summary=monthly_summary,
            priority_breakdown=priority_breakdown,
            channel_breakdown=channel_breakdown,
            tier_breakdown=tier_breakdown,
            sla_violations=sla_violations,
        )
