"""Escalation rate metrics service."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.escalation_rate import EscalationRate
from app.schemas.escalation_rate import (
    EscalationAlert,
    EscalationRateAnalyticsResponse,
    EscalationRateSummary,
    EscalationReasonBreakdown,
    EscalationTrend,
    EscalationTrendPoint,
)

logger = logging.getLogger(__name__)

# Escalation rate threshold
ESCALATION_RATE_THRESHOLD = 15.0  # 15%


class EscalationRateService:
    """Service for escalation rate metrics."""

    def __init__(self, db: AsyncSession):
        """
        Initialize escalation rate service.

        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger

    async def record_metrics(
        self,
        conversation_id: UUID,
        user_id: UUID,
        is_escalated: bool,
        escalation_reason: Optional[str],
        escalated_to: Optional[str],
        escalation_timestamp: Optional[datetime],
        total_messages: int,
        ai_responses: int,
        user_messages: int,
        channel: str,
        language: str,
        sentiment_score: Optional[float],
        confidence_score: Optional[float],
    ) -> EscalationRate:
        """
        Record escalation rate metrics for a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            is_escalated: Whether conversation was escalated
            escalation_reason: Escalation reason
            escalated_to: Escalated to (human_agent, supervisor)
            escalation_timestamp: Escalation timestamp
            total_messages: Total messages
            ai_responses: AI responses
            user_messages: User messages
            channel: Channel (web, voice, email, chat)
            language: Language
            sentiment_score: Sentiment score (-1.0 to 1.0)
            confidence_score: Confidence score (0.0 to 1.0)

        Returns:
            Created escalation rate metrics
        """
        # Convert boolean to integer
        is_escalated_int = 1 if is_escalated else 0

        # Create metrics record
        metrics = EscalationRate(
            conversation_id=conversation_id,
            user_id=user_id,
            is_escalated=is_escalated_int,
            escalation_reason=escalation_reason,
            escalated_to=escalated_to,
            escalation_timestamp=escalation_timestamp,
            total_messages=total_messages,
            ai_responses=ai_responses,
            user_messages=user_messages,
            channel=channel,
            language=language,
            sentiment_score=sentiment_score,
            confidence_score=confidence_score,
            escalation_rate_threshold=ESCALATION_RATE_THRESHOLD,
            threshold_violation=0,  # Will be checked during analytics
        )

        self.db.add(metrics)
        await self.db.commit()
        await self.db.refresh(metrics)

        self.logger.info(
            f"Escalation rate metrics recorded: conversation_id={conversation_id}, "
            f"is_escalated={is_escalated}, reason={escalation_reason}"
        )

        return metrics

    async def calculate_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        period: str,
    ) -> EscalationRateSummary:
        """
        Calculate escalation rate summary for a time period.

        Args:
            start_date: Start date
            end_date: End date
            period: Period label (daily, weekly, monthly)

        Returns:
            Escalation rate summary
        """
        query = (
            select(
                func.count(EscalationRate.id).label("total"),
                func.sum(EscalationRate.is_escalated).label("escalated"),
            )
            .where(
                EscalationRate.created_at >= start_date,
                EscalationRate.created_at <= end_date,
            )
        )

        result = await self.db.execute(query)
        row = result.one_or_none()

        if row and row.total > 0:
            total_conversations = int(row.total)
            escalated_conversations = int(row.escalated or 0)
            escalation_rate = (escalated_conversations / total_conversations) * 100
        else:
            total_conversations = 0
            escalated_conversations = 0
            escalation_rate = 0.0

        # Check threshold violation
        threshold_violation = escalation_rate > ESCALATION_RATE_THRESHOLD

        return EscalationRateSummary(
            period=period,
            start_date=start_date,
            end_date=end_date,
            total_conversations=total_conversations,
            escalated_conversations=escalated_conversations,
            escalation_rate=escalation_rate,
            threshold=ESCALATION_RATE_THRESHOLD,
            threshold_violation=threshold_violation,
        )

    async def calculate_reason_breakdown(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[EscalationReasonBreakdown]:
        """
        Calculate breakdown by escalation reason.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of escalation reason breakdowns
        """
        query = (
            select(
                EscalationRate.escalation_reason.label("reason"),
                func.count(EscalationRate.id).label("count"),
            )
            .where(
                and_(
                    EscalationRate.created_at >= start_date,
                    EscalationRate.created_at <= end_date,
                    EscalationRate.is_escalated == 1,
                )
            )
            .group_by(EscalationRate.escalation_reason)
        )

        result = await self.db.execute(query)
        breakdowns = []

        # Get total escalated count
        total_query = (
            select(func.count(EscalationRate.id))
            .where(
                and_(
                    EscalationRate.created_at >= start_date,
                    EscalationRate.created_at <= end_date,
                    EscalationRate.is_escalated == 1,
                )
            )
        )
        total_result = await self.db.execute(total_query)
        total_escalated = int(total_result.scalar() or 0)

        for row in result:
            count = int(row.count)
            percentage = (count / total_escalated * 100) if total_escalated > 0 else 0.0

            breakdowns.append(
                EscalationReasonBreakdown(
                    escalation_reason=str(row.reason) if row.reason else "unknown",
                    count=count,
                    percentage=percentage,
                )
            )

        return breakdowns

    async def calculate_trend(
        self,
        start_date: datetime,
        end_date: datetime,
        period: str,
    ) -> EscalationTrend:
        """
        Calculate escalation trend over time.

        Args:
            start_date: Start date
            end_date: End date
            period: Period (daily, weekly, monthly)

        Returns:
            Escalation trend
        """
        # Determine grouping based on period
        if period == "daily":
            date_trunc = func.date_trunc("day", EscalationRate.created_at)
        elif period == "weekly":
            date_trunc = func.date_trunc("week", EscalationRate.created_at)
        else:  # monthly
            date_trunc = func.date_trunc("month", EscalationRate.created_at)

        query = (
            select(
                date_trunc.label("date"),
                func.count(EscalationRate.id).label("total"),
                func.sum(EscalationRate.is_escalated).label("escalated"),
            )
            .where(
                EscalationRate.created_at >= start_date,
                EscalationRate.created_at <= end_date,
            )
            .group_by(date_trunc)
            .order_by(date_trunc)
        )

        result = await self.db.execute(query)
        trend_points = []

        for row in result:
            total = int(row.total)
            escalated = int(row.escalated or 0)
            escalation_rate = (escalated / total * 100) if total > 0 else 0.0

            trend_points.append(
                EscalationTrendPoint(
                    date=row.date,
                    total_conversations=total,
                    escalated_conversations=escalated,
                    escalation_rate=escalation_rate,
                )
            )

        # Calculate overall trend
        if len(trend_points) >= 2:
            first_rate = trend_points[0].escalation_rate
            last_rate = trend_points[-1].escalation_rate
            if last_rate > first_rate + 1.0:
                overall_trend = "increasing"
            elif last_rate < first_rate - 1.0:
                overall_trend = "decreasing"
            else:
                overall_trend = "stable"
        else:
            overall_trend = "stable"

        # Calculate average rate
        if trend_points:
            average_rate = sum(p.escalation_rate for p in trend_points) / len(trend_points)
        else:
            average_rate = 0.0

        return EscalationTrend(
            period=period,
            start_date=start_date,
            end_date=end_date,
            trend_points=trend_points,
            overall_trend=overall_trend,
            average_rate=average_rate,
        )

    async def check_alerts(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[EscalationAlert]:
        """
        Check for escalation rate alerts (rate > 15%).

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of alerts
        """
        alerts = []

        # Calculate escalation rate for the period
        summary = await self.calculate_summary(start_date, end_date, "alert_period")

        # Check if above threshold
        if summary.escalation_rate > ESCALATION_RATE_THRESHOLD:
            alert = EscalationAlert(
                alert_id=uuid4(),
                alert_type="escalation_rate_high",
                threshold=ESCALATION_RATE_THRESHOLD,
                current_rate=summary.escalation_rate,
                period="custom",
                start_date=start_date,
                end_date=end_date,
                triggered_at=datetime.utcnow(),
                acknowledged=False,
            )
            alerts.append(alert)

            self.logger.warning(
                f"Escalation rate alert triggered: rate={summary.escalation_rate:.2f}% "
                f"(threshold={ESCALATION_RATE_THRESHOLD}%)"
            )

        return alerts

    async def get_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> EscalationRateAnalyticsResponse:
        """
        Get complete escalation rate analytics.

        Args:
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: now)

        Returns:
            Complete escalation rate analytics
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

        # Calculate reason breakdown
        reason_breakdown = await self.calculate_reason_breakdown(start_date, end_date)

        # Calculate trend
        trend = await self.calculate_trend(start_date, end_date, "daily")

        # Check for alerts
        alerts = await self.check_alerts(start_date, end_date)

        return EscalationRateAnalyticsResponse(
            daily_summary=daily_summary,
            weekly_summary=weekly_summary,
            monthly_summary=monthly_summary,
            reason_breakdown=reason_breakdown,
            trend=trend,
            alerts=alerts,
        )
