"""Priority detection module for determining ticket priority based on various factors."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Priority detection configuration
SLA_URGENT_MINUTES = 15  # SLA for urgent tickets
SLA_HIGH_MINUTES = 60  # SLA for high priority tickets
SLA_MEDIUM_MINUTES = 240  # SLA for medium priority tickets
SLA_LOW_MINUTES = 480  # SLA for low priority tickets


class TicketPriority(str, Enum):
    """Ticket priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class PriorityReason(str, Enum):
    """Reasons for priority assignment."""

    SYSTEM_DOWN = "system_down"
    SECURITY_ISSUE = "security_issue"
    PAYMENT_FAILURE = "payment_failure"
    ANGRY_SENTIMENT = "angry_sentiment"
    MULTIPLE_ATTEMPTS = "multiple_attempts"
    REFUND_REQUEST = "refund_request"
    VIP_CUSTOMER = "vip_customer"
    TECHNICAL_ISSUE = "technical_issue"
    PRODUCT_QUESTION = "product_question"
    GENERAL_INQUIRY = "general_inquiry"
    FEATURE_REQUEST = "feature_request"
    SLA_ESCALATION = "sla_escalation"
    OVERRIDE_RULE = "override_rule"


class PriorityRule(BaseModel):
    """Priority rule definition."""

    rule_id: str = Field(description="Unique rule ID")
    priority: TicketPriority = Field(description="Priority level")
    reason: PriorityReason = Field(description="Reason for priority")
    conditions: dict[str, Any] = Field(description="Rule conditions")
    weight: float = Field(default=1.0, description="Rule weight for scoring")


class PriorityDetectionResult(BaseModel):
    """Result of priority detection."""

    detection_id: str = Field(description="Unique detection ID")
    priority: TicketPriority = Field(description="Detected priority")
    original_priority: TicketPriority = Field(description="Priority before VIP adjustment")
    reasons: list[PriorityReason] = Field(default_factory=list, description="Reasons for priority")
    score: float = Field(description="Priority score")
    customer_tier: Optional[str] = Field(default=None, description="Customer tier")
    vip_adjusted: bool = Field(default=False, description="Whether priority was adjusted for VIP")
    sla_escalated: bool = Field(default=False, description="Whether priority was escalated due to SLA")
    override_applied: bool = Field(default=False, description="Whether override rule was applied")
    override_reason: Optional[str] = Field(default=None, description="Override rule reason")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Detection timestamp")


class PriorityDetector:
    """Priority detector for determining ticket priority based on various factors."""

    def __init__(
        self,
        sla_urgent_minutes: int = SLA_URGENT_MINUTES,
        sla_high_minutes: int = SLA_HIGH_MINUTES,
        sla_medium_minutes: int = SLA_MEDIUM_MINUTES,
        sla_low_minutes: int = SLA_LOW_MINUTES,
    ):
        """
        Initialize the priority detector.

        Args:
            sla_urgent_minutes: SLA for urgent tickets
            sla_high_minutes: SLA for high priority tickets
            sla_medium_minutes: SLA for medium priority tickets
            sla_low_minutes: SLA for low priority tickets
        """
        self.sla_urgent_minutes = sla_urgent_minutes
        self.sla_high_minutes = sla_high_minutes
        self.sla_medium_minutes = sla_medium_minutes
        self.sla_low_minutes = sla_low_minutes

        # Track ticket creation times for SLA escalation
        self.ticket_creation_times: dict[str, datetime] = {}

        # Define priority rules
        self.priority_rules = self._define_priority_rules()

        # Define override rules
        self.override_rules = self._define_override_rules()

    def _define_priority_rules(self) -> list[PriorityRule]:
        """
        Define priority rules.

        Returns:
            List of priority rules
        """
        return [
            # Urgent priority rules
            PriorityRule(
                rule_id="system_down",
                priority=TicketPriority.URGENT,
                reason=PriorityReason.SYSTEM_DOWN,
                conditions={"keywords": ["system down", "outage", "service unavailable", "critical error"]},
                weight=1.0,
            ),
            PriorityRule(
                rule_id="security_issue",
                priority=TicketPriority.URGENT,
                reason=PriorityReason.SECURITY_ISSUE,
                conditions={"keywords": ["security", "hack", "breach", "unauthorized", "compromised"]},
                weight=1.0,
            ),
            PriorityRule(
                rule_id="payment_failure",
                priority=TicketPriority.URGENT,
                reason=PriorityReason.PAYMENT_FAILURE,
                conditions={"keywords": ["payment failed", "charge failed", "transaction failed", "billing error"]},
                weight=1.0,
            ),
            PriorityRule(
                rule_id="angry_sentiment",
                priority=TicketPriority.URGENT,
                reason=PriorityReason.ANGRY_SENTIMENT,
                conditions={"sentiment_class": "angry", "angry_score_threshold": 0.8},
                weight=1.0,
            ),
            # High priority rules
            PriorityRule(
                rule_id="multiple_attempts",
                priority=TicketPriority.HIGH,
                reason=PriorityReason.MULTIPLE_ATTEMPTS,
                conditions={"min_attempts": 3},
                weight=0.8,
            ),
            PriorityRule(
                rule_id="refund_request",
                priority=TicketPriority.HIGH,
                reason=PriorityReason.REFUND_REQUEST,
                conditions={"keywords": ["refund", "money back", "return", "chargeback"]},
                weight=0.9,
            ),
            # Medium priority rules
            PriorityRule(
                rule_id="technical_issue",
                priority=TicketPriority.MEDIUM,
                reason=PriorityReason.TECHNICAL_ISSUE,
                conditions={"keywords": ["bug", "error", "crash", "broken", "not working"]},
                weight=0.7,
            ),
            PriorityRule(
                rule_id="product_question",
                priority=TicketPriority.MEDIUM,
                reason=PriorityReason.PRODUCT_QUESTION,
                conditions={"keywords": ["how to", "question about", "feature", "functionality"]},
                weight=0.6,
            ),
            # Low priority rules
            PriorityRule(
                rule_id="general_inquiry",
                priority=TicketPriority.LOW,
                reason=PriorityReason.GENERAL_INQUIRY,
                conditions={"keywords": ["inquiry", "information", "ask about", "general"]},
                weight=0.5,
            ),
            PriorityRule(
                rule_id="feature_request",
                priority=TicketPriority.LOW,
                reason=PriorityReason.FEATURE_REQUEST,
                conditions={"keywords": ["feature request", "suggestion", "improvement", "enhancement"]},
                weight=0.4,
            ),
        ]

    def _define_override_rules(self) -> dict[str, dict[str, Any]]:
        """
        Define priority override rules for specific scenarios.

        Returns:
            Dictionary of override rules
        """
        return {
            "critical_system": {
                "priority": TicketPriority.URGENT,
                "conditions": {"category": "technical", "keywords": ["production", "live", "critical"]},
                "reason": "Critical system issue",
            },
            "enterprise_customer": {
                "priority": TicketPriority.HIGH,
                "conditions": {"customer_tier": "enterprise"},
                "reason": "Enterprise customer",
            },
            "repeated_issue": {
                "priority": TicketPriority.HIGH,
                "conditions": {"repeat_count": 3},
                "reason": "Repeated issue",
            },
        }

    def _check_rule_match(self, rule: PriorityRule, context: dict[str, Any]) -> bool:
        """
        Check if a rule matches the context.

        Args:
            rule: Priority rule
            context: Context data

        Returns:
            True if rule matches
        """
        conditions = rule.conditions

        # Check keyword conditions
        if "keywords" in conditions:
            message = context.get("message", "").lower()
            keywords = conditions["keywords"]
            if not any(keyword in message for keyword in keywords):
                return False

        # Check sentiment conditions
        if "sentiment_class" in conditions:
            sentiment_class = context.get("sentiment_class")
            if sentiment_class != conditions["sentiment_class"]:
                return False

        # Check angry score threshold
        if "angry_score_threshold" in conditions:
            angry_score = context.get("angry_score", 0.0)
            if angry_score < conditions["angry_score_threshold"]:
                return False

        # Check minimum attempts
        if "min_attempts" in conditions:
            attempts = context.get("attempts", 0)
            if attempts < conditions["min_attempts"]:
                return False

        return True

    def _apply_vip_adjustment(
        self,
        priority: TicketPriority,
        customer_tier: Optional[str],
    ) -> tuple[TicketPriority, bool]:
        """
        Apply VIP adjustment to priority (VIP gets one level higher).

        Args:
            priority: Original priority
            customer_tier: Customer tier

        Returns:
            Tuple of (adjusted_priority, was_adjusted)
        """
        if customer_tier == "vip":
            if priority == TicketPriority.LOW:
                return TicketPriority.MEDIUM, True
            elif priority == TicketPriority.MEDIUM:
                return TicketPriority.HIGH, True
            elif priority == TicketPriority.HIGH:
                return TicketPriority.URGENT, True
            # Urgent stays urgent

        return priority, False

    def _check_sla_escalation(
        self,
        ticket_id: str,
        current_priority: TicketPriority,
    ) -> tuple[TicketPriority, bool]:
        """
        Check if ticket should be escalated due to SLA breach.

        Args:
            ticket_id: Ticket ID
            current_priority: Current priority

        Returns:
            Tuple of (escalated_priority, was_escalated)
        """
        if ticket_id not in self.ticket_creation_times:
            return current_priority, False

        creation_time = self.ticket_creation_times[ticket_id]
        now = datetime.now(UTC)
        elapsed_minutes = (now - creation_time).total_seconds() / 60

        # Determine SLA based on priority
        sla_minutes = 0
        if current_priority == TicketPriority.URGENT:
            sla_minutes = self.sla_urgent_minutes
        elif current_priority == TicketPriority.HIGH:
            sla_minutes = self.sla_high_minutes
        elif current_priority == TicketPriority.MEDIUM:
            sla_minutes = self.sla_medium_minutes
        elif current_priority == TicketPriority.LOW:
            sla_minutes = self.sla_low_minutes

        # Check if SLA breached
        if elapsed_minutes > sla_minutes:
            # Escalate to next priority level
            if current_priority == TicketPriority.LOW:
                return TicketPriority.MEDIUM, True
            elif current_priority == TicketPriority.MEDIUM:
                return TicketPriority.HIGH, True
            elif current_priority == TicketPriority.HIGH:
                return TicketPriority.URGENT, True

        return current_priority, False

    def _apply_override_rules(
        self,
        priority: TicketPriority,
        context: dict[str, Any],
    ) -> tuple[TicketPriority, bool, Optional[str]]:
        """
        Apply override rules for specific scenarios.

        Args:
            priority: Current priority
            context: Context data

        Returns:
            Tuple of (overridden_priority, was_overridden, override_reason)
        """
        for rule_name, rule_config in self.override_rules.items():
            conditions = rule_config["conditions"]
            matches = True

            # Check all conditions
            for key, value in conditions.items():
                if key == "keywords":
                    message = context.get("message", "").lower()
                    if not any(keyword in message for keyword in value):
                        matches = False
                        break
                elif key == "category":
                    if context.get("category") != value:
                        matches = False
                        break
                elif key == "customer_tier":
                    if context.get("customer_tier") != value:
                        matches = False
                        break
                elif key == "repeat_count":
                    if context.get("repeat_count", 0) < value:
                        matches = False
                        break

            if matches:
                return rule_config["priority"], True, rule_config["reason"]

        return priority, False, None

    def detect_priority(
        self,
        message: str,
        sentiment_class: Optional[str] = None,
        angry_score: float = 0.0,
        attempts: int = 0,
        customer_tier: Optional[str] = None,
        category: Optional[str] = None,
        ticket_id: Optional[str] = None,
    ) -> PriorityDetectionResult:
        """
        Detect ticket priority based on context.

        Args:
            message: User message
            sentiment_class: Sentiment class
            angry_score: Angry sentiment score
            attempts: Number of attempts
            customer_tier: Customer tier
            category: Ticket category
            ticket_id: Ticket ID for SLA tracking

        Returns:
            Priority detection result
        """
        detection_id = str(uuid.uuid4())

        # Build context
        context = {
            "message": message,
            "sentiment_class": sentiment_class,
            "angry_score": angry_score,
            "attempts": attempts,
            "customer_tier": customer_tier,
            "category": category,
        }

        # Evaluate all rules
        matched_rules = []
        total_score = 0.0
        max_priority = TicketPriority.LOW

        for rule in self.priority_rules:
            if self._check_rule_match(rule, context):
                matched_rules.append(rule)
                total_score += rule.weight

                # Update max priority
                priority_order = [TicketPriority.LOW, TicketPriority.MEDIUM, TicketPriority.HIGH, TicketPriority.URGENT]
                current_index = priority_order.index(max_priority)
                rule_index = priority_order.index(rule.priority)
                if rule_index > current_index:
                    max_priority = rule.priority

        # Default to medium if no rules matched
        if not matched_rules:
            max_priority = TicketPriority.MEDIUM
            total_score = 0.5

        original_priority = max_priority

        # Apply VIP adjustment
        adjusted_priority, vip_adjusted = self._apply_vip_adjustment(max_priority, customer_tier)

        # Apply override rules
        final_priority, override_applied, override_reason = self._apply_override_rules(
            adjusted_priority, context
        )

        # Check SLA escalation
        if ticket_id:
            # Track creation time if not tracked
            if ticket_id not in self.ticket_creation_times:
                self.ticket_creation_times[ticket_id] = datetime.now(UTC)

            final_priority, sla_escalated = self._check_sla_escalation(ticket_id, final_priority)
        else:
            sla_escalated = False

        # Collect reasons
        reasons = [rule.reason for rule in matched_rules]
        if vip_adjusted:
            reasons.append(PriorityReason.VIP_CUSTOMER)
        if sla_escalated:
            reasons.append(PriorityReason.SLA_ESCALATION)
        if override_applied:
            reasons.append(PriorityReason.OVERRIDE_RULE)

        # Create result
        result = PriorityDetectionResult(
            detection_id=detection_id,
            priority=final_priority,
            original_priority=original_priority,
            reasons=reasons,
            score=total_score,
            customer_tier=customer_tier,
            vip_adjusted=vip_adjusted,
            sla_escalated=sla_escalated,
            override_applied=override_applied,
            override_reason=override_reason,
        )

        logger.info(
            f"Priority detected: {final_priority.value}, "
            f"original: {original_priority.value}, "
            f"score: {total_score:.2f}, "
            f"vip_adjusted: {vip_adjusted}, "
            f"sla_escalated: {sla_escalated}, "
            f"override_applied: {override_applied}"
        )

        return result

    def track_ticket_creation(self, ticket_id: str) -> None:
        """
        Track ticket creation time for SLA monitoring.

        Args:
            ticket_id: Ticket ID
        """
        self.ticket_creation_times[ticket_id] = datetime.now(UTC)
        logger.info(f"Ticket creation tracked: {ticket_id}")

    def remove_ticket_tracking(self, ticket_id: str) -> None:
        """
        Remove ticket from SLA tracking.

        Args:
            ticket_id: Ticket ID
        """
        if ticket_id in self.ticket_creation_times:
            del self.ticket_creation_times[ticket_id]
            logger.info(f"Ticket tracking removed: {ticket_id}")
