"""Angry customer handler for detecting and managing angry customers."""

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Angry customer configuration
ANGRY_THRESHOLD = 0.8  # Threshold for angry sentiment to trigger action
CRITICAL_PRIORITY = 10  # Priority level for angry customers (highest)
ESCALATION_CHANNELS = ["slack", "email", "teams"]  # Notification channels


class AngryCustomerAction(str, Enum):
    """Actions to take when angry customer is detected."""

    ESCALATE_PRIORITY = "escalate_priority"
    NOTIFY_SUPERVISOR = "notify_supervisor"
    ADD_DASHBOARD_FLAG = "add_dashboard_flag"
    OPTIMIZE_WORKFLOW = "optimize_workflow"
    TAG_TICKET = "tag_ticket"


class SupervisorNotification(BaseModel):
    """Supervisor notification details."""

    notification_id: str = Field(description="Unique notification ID")
    conversation_id: str = Field(description="Conversation ID")
    user_id: str = Field(description="User ID")
    angry_score: float = Field(description="Angry sentiment score")
    message: str = Field(description="Customer message that triggered alert")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Notification timestamp")
    channel: str = Field(description="Notification channel (slack/email/teams)")
    status: str = Field(default="pending", description="Notification status")
    supervisor_id: Optional[str] = Field(default=None, description="Supervisor ID")


class AngryCustomerFlag(BaseModel):
    """Visual flag for agent dashboard."""

    flag_id: str = Field(description="Unique flag ID")
    conversation_id: str = Field(description="Conversation ID")
    flag_type: str = Field(default="angry_customer", description="Flag type")
    severity: str = Field(description="Severity level (low/medium/high/critical)")
    angry_score: float = Field(description="Angry sentiment score")
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="When flag was triggered")
    actions_taken: list[str] = Field(default_factory=list, description="Actions taken")
    is_active: bool = Field(default=True, description="Whether flag is active")


class AngryCustomerHandler:
    """Handler for detecting and managing angry customers."""

    def __init__(
        self,
        angry_threshold: float = ANGRY_THRESHOLD,
        critical_priority: int = CRITICAL_PRIORITY,
    ):
        """
        Initialize the angry customer handler.

        Args:
            angry_threshold: Threshold for angry sentiment to trigger action
            critical_priority: Priority level for angry customers
        """
        self.angry_threshold = angry_threshold
        self.critical_priority = critical_priority

    def is_angry_customer(
        self,
        sentiment_scores: dict[str, float],
    ) -> bool:
        """
        Check if customer is angry based on sentiment scores.

        Args:
            sentiment_scores: Sentiment scores for all classes

        Returns:
            True if customer is angry
        """
        angry_score = sentiment_scores.get("angry", 0.0)
        return angry_score >= self.angry_threshold

    def escalate_priority(
        self,
        current_priority: int,
    ) -> int:
        """
        Escalate conversation priority to critical.

        Args:
            current_priority: Current priority level

        Returns:
            Escalated priority level
        """
        logger.info(f"Escalating priority from {current_priority} to {self.critical_priority}")
        return self.critical_priority

    async def notify_supervisor(
        self,
        conversation_id: str,
        user_id: str,
        angry_score: float,
        message: str,
        channel: str = "slack",
    ) -> SupervisorNotification:
        """
        Notify supervisor about angry customer.

        Args:
            conversation_id: The conversation ID
            user_id: The user ID
            angry_score: Angry sentiment score
            message: Customer message that triggered alert
            channel: Notification channel (slack/email/teams)

        Returns:
            Supervisor notification details
        """
        import uuid

        notification = SupervisorNotification(
            notification_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            user_id=user_id,
            angry_score=angry_score,
            message=message,
            channel=channel,
        )

        # TODO: Implement actual notification sending
        # For now, log the notification
        logger.warning(
            f"ANGRY CUSTOMER ALERT - Channel: {channel}, "
            f"Conversation: {conversation_id}, User: {user_id}, "
            f"Angry Score: {angry_score:.2f}, Message: {message[:100]}..."
        )

        # Placeholder for actual notification implementation
        # Slack: Use Slack API webhook
        # Email: Use email service
        # Teams: Use Teams webhook

        notification.status = "sent"
        return notification

    def add_dashboard_flag(
        self,
        conversation_id: str,
        angry_score: float,
    ) -> AngryCustomerFlag:
        """
        Add visual flag to agent dashboard.

        Args:
            conversation_id: The conversation ID
            angry_score: Angry sentiment score

        Returns:
            Dashboard flag details
        """
        import uuid

        # Determine severity based on angry score
        if angry_score >= 0.9:
            severity = "critical"
        elif angry_score >= 0.85:
            severity = "high"
        else:
            severity = "medium"

        flag = AngryCustomerFlag(
            flag_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            severity=severity,
            angry_score=angry_score,
        )

        logger.info(
            f"Added dashboard flag for conversation {conversation_id}: "
            f"severity={severity}, angry_score={angry_score:.2f}"
        )

        return flag

    def optimize_workflow(
        self,
        current_workflow_nodes: list[str],
    ) -> list[str]:
        """
        Optimize workflow by skipping non-essential nodes for angry customers.

        Args:
            current_workflow_nodes: Current workflow node sequence

        Returns:
            Optimized workflow node sequence
        """
        # Non-essential nodes to skip for angry customers
        non_essential_nodes = [
            "knowledge_search",  # Skip knowledge search for faster response
            "context_management",  # Skip context loading for speed
            "customer_profile",  # Skip profile loading for speed
        ]

        optimized_nodes = [
            node for node in current_workflow_nodes
            if node not in non_essential_nodes
        ]

        logger.info(
            f"Optimized workflow: skipped {len(current_workflow_nodes) - len(optimized_nodes)} nodes, "
            f"reduced from {len(current_workflow_nodes)} to {len(optimized_nodes)} nodes"
        )

        return optimized_nodes

    def get_ticket_sentiment_tag(
        self,
        sentiment_class: str,
        angry_score: float,
    ) -> str:
        """
        Get sentiment tag for ticket creation.

        Args:
            sentiment_class: Sentiment class
            angry_score: Angry sentiment score

        Returns:
            Sentiment tag for ticket
        """
        if angry_score >= self.angry_threshold:
            return "angry_customer"
        elif sentiment_class == "negative":
            return "negative_sentiment"
        elif sentiment_class == "positive":
            return "positive_sentiment"
        else:
            return "neutral_sentiment"

    async def handle_angry_customer(
        self,
        conversation_id: str,
        user_id: str,
        sentiment_scores: dict[str, float],
        sentiment_class: str,
        message: str,
        current_priority: int,
        current_workflow_nodes: Optional[list[str]] = None,
        notification_channels: list[str] = ESCALATION_CHANNELS,
    ) -> dict[str, Any]:
        """
        Handle angry customer detection and take appropriate actions.

        Args:
            conversation_id: The conversation ID
            user_id: The user ID
            sentiment_scores: Sentiment scores
            sentiment_class: Sentiment class
            message: Customer message
            current_priority: Current priority level
            current_workflow_nodes: Current workflow nodes
            notification_channels: Notification channels for supervisor

        Returns:
            Dictionary of actions taken
        """
        actions_taken = []
        results = {}

        # Check if customer is angry
        if not self.is_angry_customer(sentiment_scores):
            logger.info(f"Customer not angry (angry score: {sentiment_scores.get('angry', 0.0):.2f})")
            return {"is_angry": False, "actions_taken": []}

        angry_score = sentiment_scores.get("angry", 0.0)
        logger.warning(f"ANGRY CUSTOMER DETECTED: {conversation_id} (angry score: {angry_score:.2f})")

        # 1. Escalate priority
        new_priority = self.escalate_priority(current_priority)
        actions_taken.append(AngryCustomerAction.ESCALATE_PRIORITY.value)
        results["priority"] = new_priority

        # 2. Notify supervisor
        notifications = []
        for channel in notification_channels:
            notification = await self.notify_supervisor(
                conversation_id=conversation_id,
                user_id=user_id,
                angry_score=angry_score,
                message=message,
                channel=channel,
            )
            notifications.append(notification.model_dump())
        actions_taken.append(AngryCustomerAction.NOTIFY_SUPERVISOR.value)
        results["notifications"] = notifications

        # 3. Add dashboard flag
        dashboard_flag = self.add_dashboard_flag(conversation_id, angry_score)
        actions_taken.append(AngryCustomerAction.ADD_DASHBOARD_FLAG.value)
        results["dashboard_flag"] = dashboard_flag.model_dump()

        # 4. Optimize workflow
        if current_workflow_nodes:
            optimized_nodes = self.optimize_workflow(current_workflow_nodes)
            actions_taken.append(AngryCustomerAction.OPTIMIZE_WORKFLOW.value)
            results["optimized_workflow"] = optimized_nodes

        # 5. Get ticket sentiment tag
        ticket_tag = self.get_ticket_sentiment_tag(sentiment_class, angry_score)
        actions_taken.append(AngryCustomerAction.TAG_TICKET.value)
        results["ticket_tag"] = ticket_tag

        logger.info(
            f"Angry customer handling completed: {len(actions_taken)} actions taken for {conversation_id}"
        )

        return {
            "is_angry": True,
            "angry_score": angry_score,
            "actions_taken": actions_taken,
            "results": results,
        }
