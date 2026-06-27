"""CSAT (Customer Satisfaction) service for survey collection and analytics."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.csat import CSATSurvey
from app.schemas.csat import (
    CSATAlert,
    CSATAnalyticsResponse,
    CSATBreakdown,
    CSATMetrics,
    CSATTrend,
    CSATTrendPoint,
)

logger = logging.getLogger(__name__)

# CSAT configuration
CSAT_SCALE_MIN = 1
CSAT_SCALE_MAX = 5
CSAT_ALERT_THRESHOLD = 4.0  # Alert if CSAT drops below 4.0


class CSATService:
    """Service for CSAT survey collection and analytics."""

    def __init__(self, db: AsyncSession):
        """
        Initialize CSAT service.

        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger

    async def submit_survey(
        self,
        conversation_id: UUID,
        user_id: UUID,
        score: int,
        feedback: Optional[str],
        channel: str,
        language: str,
        agent_type: str,
        agent_id: Optional[UUID],
    ) -> CSATSurvey:
        """
        Submit a CSAT survey response.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            score: CSAT score (1-5)
            feedback: Optional text feedback
            channel: Channel (web, voice, email, chat)
            language: Language (en, hi, etc.)
            agent_type: Agent type (ai, human)
            agent_id: Agent ID if human

        Returns:
            Created CSAT survey
        """
        # Validate score
        if not CSAT_SCALE_MIN <= score <= CSAT_SCALE_MAX:
            raise ValueError(f"Score must be between {CSAT_SCALE_MIN} and {CSAT_SCALE_MAX}")

        # Create survey
        survey = CSATSurvey(
            conversation_id=conversation_id,
            user_id=user_id,
            score=score,
            feedback=feedback,
            channel=channel,
            language=language,
            agent_type=agent_type,
            agent_id=agent_id,
            survey_sent_at=datetime.utcnow(),
            survey_completed_at=datetime.utcnow(),
        )

        self.db.add(survey)
        await self.db.commit()
        await self.db.refresh(survey)

        self.logger.info(
            f"CSAT survey submitted: conversation_id={conversation_id}, "
            f"score={score}, channel={channel}, language={language}, agent_type={agent_type}"
        )

        return survey

    async def calculate_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
        period: str,
    ) -> CSATMetrics:
        """
        Calculate CSAT metrics for a time period.

        Args:
            start_date: Start date
            end_date: End date
            period: Period label (daily, weekly, monthly)

        Returns:
            CSAT metrics
        """
        query = (
            select(
                func.avg(CSATSurvey.score).label("avg_score"),
                func.count(CSATSurvey.id).label("total_surveys"),
            )
            .where(
                CSATSurvey.survey_completed_at >= start_date,
                CSATSurvey.survey_completed_at <= end_date,
            )
        )

        result = await self.db.execute(query)
        row = result.one_or_none()

        if row and row.total_surveys > 0:
            average_score = float(row.avg_score)
            total_surveys = int(row.total_surveys)
        else:
            average_score = 0.0
            total_surveys = 0

        # Get score distribution
        distribution_query = (
            select(CSATSurvey.score, func.count(CSATSurvey.id))
            .where(
                CSATSurvey.survey_completed_at >= start_date,
                CSATSurvey.survey_completed_at <= end_date,
            )
            .group_by(CSATSurvey.score)
        )

        distribution_result = await self.db.execute(distribution_query)
        score_distribution = {row[0]: row[1] for row in distribution_result}

        return CSATMetrics(
            period=period,
            start_date=start_date,
            end_date=end_date,
            average_score=average_score,
            total_surveys=total_surveys,
            score_distribution=score_distribution,
        )

    async def calculate_breakdown(
        self,
        start_date: datetime,
        end_date: datetime,
        dimension: str,
    ) -> list[CSATBreakdown]:
        """
        Calculate CSAT breakdown by dimension.

        Args:
            start_date: Start date
            end_date: End date
            dimension: Dimension (channel, language, agent_type)

        Returns:
            List of breakdowns
        """
        # Map dimension to column
        dimension_column = {
            "channel": CSATSurvey.channel,
            "language": CSATSurvey.language,
            "agent_type": CSATSurvey.agent_type,
        }.get(dimension)

        if not dimension_column:
            raise ValueError(f"Invalid dimension: {dimension}")

        query = (
            select(
                dimension_column.label("dimension_value"),
                func.avg(CSATSurvey.score).label("avg_score"),
                func.count(CSATSurvey.id).label("total_surveys"),
            )
            .where(
                CSATSurvey.survey_completed_at >= start_date,
                CSATSurvey.survey_completed_at <= end_date,
            )
            .group_by(dimension_column)
        )

        result = await self.db.execute(query)
        breakdowns = []

        for row in result:
            breakdowns.append(
                CSATBreakdown(
                    dimension=dimension,
                    value=str(row.dimension_value),
                    average_score=float(row.avg_score),
                    total_surveys=int(row.total_surveys),
                    trend="stable",  # Placeholder for trend calculation
                )
            )

        return breakdowns

    async def calculate_trend(
        self,
        start_date: datetime,
        end_date: datetime,
        period: str,
    ) -> CSATTrend:
        """
        Calculate CSAT trend over time.

        Args:
            start_date: Start date
            end_date: End date
            period: Period (daily, weekly, monthly)

        Returns:
            CSAT trend
        """
        # Determine grouping based on period
        if period == "daily":
            date_trunc = func.date_trunc("day", CSATSurvey.survey_completed_at)
            interval = timedelta(days=1)
        elif period == "weekly":
            date_trunc = func.date_trunc("week", CSATSurvey.survey_completed_at)
            interval = timedelta(weeks=1)
        else:  # monthly
            date_trunc = func.date_trunc("month", CSATSurvey.survey_completed_at)
            interval = timedelta(days=30)

        query = (
            select(
                date_trunc.label("date"),
                func.avg(CSATSurvey.score).label("avg_score"),
                func.count(CSATSurvey.id).label("total_surveys"),
            )
            .where(
                CSATSurvey.survey_completed_at >= start_date,
                CSATSurvey.survey_completed_at <= end_date,
            )
            .group_by(date_trunc)
            .order_by(date_trunc)
        )

        result = await self.db.execute(query)
        trend_points = []

        for row in result:
            trend_points.append(
                CSATTrendPoint(
                    date=row.date,
                    average_score=float(row.avg_score),
                    total_surveys=int(row.total_surveys),
                )
            )

        # Calculate overall trend
        if len(trend_points) >= 2:
            first_score = trend_points[0].average_score
            last_score = trend_points[-1].average_score
            if last_score > first_score + 0.1:
                overall_trend = "up"
            elif last_score < first_score - 0.1:
                overall_trend = "down"
            else:
                overall_trend = "stable"
        else:
            overall_trend = "stable"

        # Calculate average over period
        if trend_points:
            average_score = sum(p.average_score for p in trend_points) / len(trend_points)
        else:
            average_score = 0.0

        return CSATTrend(
            period=period,
            start_date=start_date,
            end_date=end_date,
            trend_points=trend_points,
            overall_trend=overall_trend,
            average_score=average_score,
        )

    async def check_alerts(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CSATAlert]:
        """
        Check for CSAT alerts (score below threshold).

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of alerts
        """
        alerts = []

        # Calculate average CSAT for the period
        metrics = await self.calculate_metrics(start_date, end_date, "alert_period")

        # Check if below threshold
        if metrics.average_score > 0 and metrics.average_score < CSAT_ALERT_THRESHOLD:
            alert = CSATAlert(
                alert_id=uuid4(),
                alert_type="csat_drop",
                threshold=CSAT_ALERT_THRESHOLD,
                current_score=metrics.average_score,
                period="custom",
                start_date=start_date,
                end_date=end_date,
                triggered_at=datetime.utcnow(),
                acknowledged=False,
            )
            alerts.append(alert)

            self.logger.warning(
                f"CSAT alert triggered: score={metrics.average_score:.2f} "
                f"(threshold={CSAT_ALERT_THRESHOLD})"
            )

        return alerts

    async def get_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> CSATAnalyticsResponse:
        """
        Get complete CSAT analytics.

        Args:
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: now)

        Returns:
            Complete CSAT analytics
        """
        # Set default dates
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Calculate metrics
        daily_metrics = await self.calculate_metrics(
            start_date=end_date - timedelta(days=1),
            end_date=end_date,
            period="daily",
        )

        weekly_metrics = await self.calculate_metrics(
            start_date=end_date - timedelta(weeks=1),
            end_date=end_date,
            period="weekly",
        )

        monthly_metrics = await self.calculate_metrics(
            start_date=end_date - timedelta(days=30),
            end_date=end_date,
            period="monthly",
        )

        # Calculate breakdowns
        channel_breakdown = await self.calculate_breakdown(start_date, end_date, "channel")
        language_breakdown = await self.calculate_breakdown(start_date, end_date, "language")
        agent_breakdown = await self.calculate_breakdown(start_date, end_date, "agent_type")

        # Calculate trend
        trend = await self.calculate_trend(start_date, end_date, "daily")

        # Check for alerts
        alerts = await self.check_alerts(start_date, end_date)

        return CSATAnalyticsResponse(
            daily_metrics=daily_metrics,
            weekly_metrics=weekly_metrics,
            monthly_metrics=monthly_metrics,
            channel_breakdown=channel_breakdown,
            language_breakdown=language_breakdown,
            agent_breakdown=agent_breakdown,
            trend=trend,
            alerts=alerts,
        )
