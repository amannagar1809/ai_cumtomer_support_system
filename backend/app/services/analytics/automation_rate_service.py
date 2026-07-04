"""Automation rate metrics service."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation_rate import AutomationRate
from app.schemas.automation_rate import (
    AutomationRateAnalyticsResponse,
    AutomationRateSummary,
    AutomationTypeBreakdown,
    CostSavings,
    IntentCategoryTarget,
)

logger = logging.getLogger(__name__)

# Default agent cost per hour
DEFAULT_AGENT_COST_PER_HOUR = 25.0  # $25/hour

# Default automation targets by intent category
DEFAULT_AUTOMATION_TARGETS = {
    "faq": 90.0,  # 90% automation target for FAQs
    "account_management": 80.0,  # 80% for account management
    "billing": 75.0,  # 75% for billing
    "technical_support": 60.0,  # 60% for technical support
    "complaint": 40.0,  # 40% for complaints
    "general_inquiry": 70.0,  # 70% for general inquiries
}


class AutomationRateService:
    """Service for automation rate metrics."""

    def __init__(self, db: AsyncSession):
        """
        Initialize automation rate service.

        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger

    async def record_metrics(
        self,
        conversation_id: UUID,
        user_id: UUID,
        automation_type: str,
        total_messages: int,
        ai_messages: int,
        human_messages: int,
        conversation_duration_seconds: Optional[float],
        intent_category: Optional[str],
        predicted_intent: Optional[str],
        estimated_human_time_minutes: Optional[float],
        actual_human_time_minutes: Optional[float],
        agent_cost_per_hour: float,
        channel: str,
        language: str,
    ) -> AutomationRate:
        """
        Record automation rate metrics for a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            automation_type: Automation type (fully_automated, hybrid, human_only)
            total_messages: Total messages
            ai_messages: AI messages
            human_messages: Human messages
            conversation_duration_seconds: Conversation duration in seconds
            intent_category: Intent category for target tracking
            predicted_intent: Predicted intent
            estimated_human_time_minutes: Estimated time if handled by human
            actual_human_time_minutes: Actual human time spent
            agent_cost_per_hour: Agent cost per hour
            channel: Channel (web, voice, email, chat)
            language: Language

        Returns:
            Created automation rate metrics
        """
        # Calculate cost savings
        cost_savings = None
        if estimated_human_time_minutes and actual_human_time_minutes is not None:
            time_saved_minutes = estimated_human_time_minutes - actual_human_time_minutes
            if time_saved_minutes > 0:
                time_saved_hours = time_saved_minutes / 60
                cost_savings = time_saved_hours * agent_cost_per_hour

        # Get automation target for this category
        automation_target = DEFAULT_AUTOMATION_TARGETS.get(intent_category) if intent_category else None

        # Create metrics record
        metrics = AutomationRate(
            conversation_id=conversation_id,
            user_id=user_id,
            automation_type=automation_type,
            total_messages=total_messages,
            ai_messages=ai_messages,
            human_messages=human_messages,
            conversation_duration_seconds=conversation_duration_seconds,
            intent_category=intent_category,
            predicted_intent=predicted_intent,
            estimated_human_time_minutes=estimated_human_time_minutes,
            actual_human_time_minutes=actual_human_time_minutes,
            agent_cost_per_hour=agent_cost_per_hour,
            cost_savings=cost_savings,
            channel=channel,
            language=language,
            automation_target=automation_target,
        )

        self.db.add(metrics)
        await self.db.commit()
        await self.db.refresh(metrics)

        self.logger.info(
            f"Automation rate metrics recorded: conversation_id={conversation_id}, "
            f"type={automation_type}, savings={cost_savings:.2f}"
        )

        return metrics

    async def calculate_summary(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> AutomationRateSummary:
        """
        Calculate automation rate summary for a time period.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Automation rate summary
        """
        # Get total count by type
        query = (
            select(
                AutomationRate.automation_type.label("type"),
                func.count(AutomationRate.id).label("count"),
            )
            .where(
                AutomationRate.created_at >= start_date,
                AutomationRate.created_at <= end_date,
            )
            .group_by(AutomationRate.automation_type)
        )

        result = await self.db.execute(query)
        type_counts = {row.type: int(row.count) for row in result}

        # Calculate totals
        total_conversations = sum(type_counts.values())
        fully_automated = type_counts.get("fully_automated", 0)
        hybrid = type_counts.get("hybrid", 0)
        human_only = type_counts.get("human_only", 0)

        # Calculate automation rate (fully automated / total)
        automation_rate = (fully_automated / total_conversations * 100) if total_conversations > 0 else 0.0

        # Build type breakdown
        type_breakdown = []
        for auto_type, count in type_counts.items():
            percentage = (count / total_conversations * 100) if total_conversations > 0 else 0.0
            type_breakdown.append(
                AutomationTypeBreakdown(
                    automation_type=auto_type,
                    count=count,
                    percentage=percentage,
                )
            )

        return AutomationRateSummary(
            period="monthly",
            start_date=start_date,
            end_date=end_date,
            total_conversations=total_conversations,
            fully_automated=fully_automated,
            hybrid=hybrid,
            human_only=human_only,
            automation_rate=automation_rate,
            type_breakdown=type_breakdown,
        )

    async def calculate_cost_savings(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> CostSavings:
        """
        Calculate cost savings for a time period.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Cost savings metrics
        """
        # Get total cost savings and agent cost
        query = (
            select(
                func.sum(AutomationRate.cost_savings).label("total_savings"),
                func.avg(AutomationRate.agent_cost_per_hour).label("avg_cost"),
                func.count(AutomationRate.id).label("total_conversations"),
            )
            .where(
                AutomationRate.created_at >= start_date,
                AutomationRate.created_at <= end_date,
                AutomationRate.cost_savings.isnot(None),
            )
        )

        result = await self.db.execute(query)
        row = result.one_or_none()

        if row and row.total_conversations > 0:
            total_cost_savings = float(row.total_savings or 0)
            avg_cost_per_hour = float(row.avg_cost or DEFAULT_AGENT_COST_PER_HOUR)
            total_conversations = int(row.total_conversations)
            
            # Calculate hours saved
            total_hours_saved = total_cost_savings / avg_cost_per_hour if avg_cost_per_hour > 0 else 0.0
            
            # Calculate average cost per conversation
            avg_cost_per_conversation = total_cost_savings / total_conversations if total_conversations > 0 else 0.0
        else:
            total_cost_savings = 0.0
            total_hours_saved = 0.0
            avg_cost_per_conversation = 0.0
            avg_cost_per_hour = DEFAULT_AGENT_COST_PER_HOUR
            total_conversations = 0

        return CostSavings(
            period="monthly",
            start_date=start_date,
            end_date=end_date,
            total_hours_saved=total_hours_saved,
            total_cost_savings=total_cost_savings,
            avg_cost_per_conversation=avg_cost_per_conversation,
            agent_cost_per_hour=avg_cost_per_hour,
        )

    async def calculate_intent_category_targets(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[IntentCategoryTarget]:
        """
        Calculate automation targets by intent category.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of intent category targets
        """
        # Get counts by category and automation type
        query = (
            select(
                AutomationRate.intent_category.label("category"),
                AutomationRate.automation_type.label("type"),
                func.count(AutomationRate.id).label("count"),
            )
            .where(
                and_(
                    AutomationRate.created_at >= start_date,
                    AutomationRate.created_at <= end_date,
                    AutomationRate.intent_category.isnot(None),
                )
            )
            .group_by(AutomationRate.intent_category, AutomationRate.automation_type)
        )

        result = await self.db.execute(query)
        category_data = {}

        for row in result:
            category = str(row.category)
            if category not in category_data:
                category_data[category] = {"total": 0, "automated": 0}
            category_data[category]["total"] += int(row.count)
            if row.type == "fully_automated":
                category_data[category]["automated"] += int(row.count)

        # Build targets
        targets = []
        for category, data in category_data.items():
            total = data["total"]
            automated = data["automated"]
            actual_rate = (automated / total * 100) if total > 0 else 0.0
            target_rate = DEFAULT_AUTOMATION_TARGETS.get(category, 70.0)
            gap = target_rate - actual_rate

            targets.append(
                IntentCategoryTarget(
                    intent_category=category,
                    target_rate=target_rate,
                    actual_rate=actual_rate,
                    gap=gap,
                    total_conversations=total,
                    automated_conversations=automated,
                )
            )

        return targets

    async def get_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> AutomationRateAnalyticsResponse:
        """
        Get complete automation rate analytics.

        Args:
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: now)

        Returns:
            Complete automation rate analytics
        """
        # Set default dates (monthly)
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Calculate summary
        monthly_summary = await self.calculate_summary(start_date, end_date)

        # Calculate cost savings
        cost_savings = await self.calculate_cost_savings(start_date, end_date)

        # Calculate intent category targets
        intent_category_targets = await self.calculate_intent_category_targets(start_date, end_date)

        return AutomationRateAnalyticsResponse(
            monthly_summary=monthly_summary,
            cost_savings=cost_savings,
            intent_category_targets=intent_category_targets,
        )
