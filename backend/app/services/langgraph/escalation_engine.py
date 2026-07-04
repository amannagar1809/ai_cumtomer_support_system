"""Escalation engine for automatic escalation based on AI confidence."""

import difflib
import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Confidence thresholds
MIN_CONFIDENCE_THRESHOLD = 0.70
IMMEDIATE_ESCALATION_THRESHOLD = 0.60
REPHRASE_THRESHOLD_LOW = 0.60
REPHRASE_THRESHOLD_HIGH = 0.70
CONSECUTIVE_LOW_CONFIDENCE_LIMIT = 2

# VIP-specific thresholds
VIP_MIN_CONFIDENCE_THRESHOLD = 0.80
VIP_IMMEDIATE_ESCALATION_THRESHOLD = 0.70
VIP_REPHRASE_THRESHOLD_LOW = 0.70
VIP_REPHRASE_THRESHOLD_HIGH = 0.80
VIP_CONSECUTIVE_LOW_CONFIDENCE_LIMIT = 1

# Failed attempt thresholds
FAILED_ATTEMPT_LIMIT = 3
VIP_FAILED_ATTEMPT_LIMIT = 2
MESSAGE_SIMILARITY_THRESHOLD = 0.8  # 80% similarity threshold

# Customer types
CUSTOMER_TYPE_REGULAR = "regular"
CUSTOMER_TYPE_PREMIUM = "premium"
CUSTOMER_TYPE_VIP = "vip"
CUSTOMER_TYPE_ENTERPRISE = "enterprise"

# VIP customer types (get preferential treatment)
VIP_CUSTOMER_TYPES = [CUSTOMER_TYPE_VIP, CUSTOMER_TYPE_ENTERPRISE]

# Agent team routing
AGENT_TEAM_GENERAL = "general"
AGENT_TEAM_VIP = "vip_dedicated"
AGENT_TEAM_ENTERPRISE = "enterprise_dedicated"


class EscalationReason(str, Enum):
    """Reason for escalation."""

    LOW_CONFIDENCE = "low_confidence"
    CONSECUTIVE_LOW_CONFIDENCE = "consecutive_low_confidence"
    REPHRASE_FAILED = "rephrase_failed"
    FAILED_ATTEMPTS = "failed_attempts"
    ANGRY_CUSTOMER = "angry_customer"
    HIGH_PRIORITY_CUSTOMER = "high_priority_customer"
    VIP_CUSTOMER = "vip_customer"
    COMPLEX_QUERY = "complex_query"
    MANUAL_REQUEST = "manual_request"
    SYSTEM_ERROR = "system_error"


class EscalationDecision(BaseModel):
    """Escalation decision model."""

    should_escalate: bool = Field(description="Whether to escalate to human")
    reason: Optional[EscalationReason] = Field(default=None, description="Reason for escalation")
    confidence_score: float = Field(description="AI confidence score")
    rephrase_attempted: bool = Field(default=False, description="Whether rephrase was attempted")
    rephrase_confidence: Optional[float] = Field(default=None, description="Confidence after rephrase")
    low_confidence_count: int = Field(default=0, description="Count of consecutive low-confidence messages")
    failed_attempt_count: int = Field(default=0, description="Count of failed attempts")
    message: str = Field(default="", description="Escalation message to user")
    escalation_payload: dict = Field(default_factory=dict, description="Additional escalation payload data")
    is_vip: bool = Field(default=False, description="Whether customer is VIP")
    customer_type: Optional[str] = Field(default=None, description="Customer type")


class LowConfidenceQuery(BaseModel):
    """Low confidence query for logging and model improvement."""

    query_id: str = Field(description="Unique query ID")
    conversation_id: str = Field(description="Conversation ID")
    user_id: str = Field(description="User ID")
    query: str = Field(description="Original user query")
    confidence_score: float = Field(description="AI confidence score")
    rephrase_attempted: bool = Field(default=False, description="Whether rephrase was attempted")
    rephrase_confidence: Optional[float] = Field(default=None, description="Confidence after rephrase")
    escalated: bool = Field(default=False, description="Whether query was escalated")
    escalation_reason: Optional[str] = Field(default=None, description="Reason for escalation")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Query timestamp")
    context: dict = Field(default_factory=dict, description="Additional context")


class EscalationEngine:
    """Escalation engine for automatic escalation based on AI confidence."""

    def __init__(
        self,
        min_confidence_threshold: float = MIN_CONFIDENCE_THRESHOLD,
        immediate_escalation_threshold: float = IMMEDIATE_ESCALATION_THRESHOLD,
        consecutive_low_confidence_limit: int = CONSECUTIVE_LOW_CONFIDENCE_LIMIT,
        failed_attempt_limit: int = FAILED_ATTEMPT_LIMIT,
        message_similarity_threshold: float = MESSAGE_SIMILARITY_THRESHOLD,
        customer_type: Optional[str] = None,
    ):
        """
        Initialize escalation engine.

        Args:
            min_confidence_threshold: Minimum confidence threshold for AI response
            immediate_escalation_threshold: Threshold for immediate escalation
            consecutive_low_confidence_limit: Limit for consecutive low-confidence before escalation
            failed_attempt_limit: Limit for failed attempts before escalation
            message_similarity_threshold: Threshold for message similarity detection
            customer_type: Customer type (regular, premium, vip, enterprise)
        """
        self.customer_type = customer_type
        self.is_vip = self._is_vip_customer(customer_type)

        # Set thresholds based on customer type
        if self.is_vip:
            self.min_confidence_threshold = VIP_MIN_CONFIDENCE_THRESHOLD
            self.immediate_escalation_threshold = VIP_IMMEDIATE_ESCALATION_THRESHOLD
            self.rephrase_threshold_low = VIP_REPHRASE_THRESHOLD_LOW
            self.rephrase_threshold_high = VIP_REPHRASE_THRESHOLD_HIGH
            self.consecutive_low_confidence_limit = VIP_CONSECUTIVE_LOW_CONFIDENCE_LIMIT
            self.failed_attempt_limit = VIP_FAILED_ATTEMPT_LIMIT
        else:
            self.min_confidence_threshold = min_confidence_threshold
            self.immediate_escalation_threshold = immediate_escalation_threshold
            self.rephrase_threshold_low = REPHRASE_THRESHOLD_LOW
            self.rephrase_threshold_high = REPHRASE_THRESHOLD_HIGH
            self.consecutive_low_confidence_limit = consecutive_low_confidence_limit
            self.failed_attempt_limit = failed_attempt_limit

        self.message_similarity_threshold = message_similarity_threshold

    def _is_vip_customer(self, customer_type: Optional[str]) -> bool:
        """
        Check if customer is VIP (gets preferential treatment).

        Args:
            customer_type: Customer type

        Returns:
            True if customer is VIP or enterprise
        """
        if not customer_type:
            return False
        return customer_type.lower() in [ct.lower() for ct in VIP_CUSTOMER_TYPES]

    def get_agent_team(self) -> str:
        """
        Get the appropriate agent team for escalation routing.

        Returns:
            Agent team name based on customer type
        """
        if not self.customer_type:
            return AGENT_TEAM_GENERAL

        customer_type_lower = self.customer_type.lower()

        if customer_type_lower == CUSTOMER_TYPE_ENTERPRISE:
            return AGENT_TEAM_ENTERPRISE
        elif customer_type_lower == CUSTOMER_TYPE_VIP:
            return AGENT_TEAM_VIP
        else:
            return AGENT_TEAM_GENERAL

    def evaluate_confidence(
        self,
        confidence: float,
        low_confidence_count: int,
        rephrase_attempted: bool = False,
        rephrase_confidence: Optional[float] = None,
    ) -> EscalationDecision:
        """
        Evaluate AI confidence and make escalation decision.

        Args:
            confidence: AI confidence score
            low_confidence_count: Count of consecutive low-confidence messages
            rephrase_attempted: Whether rephrase was attempted
            rephrase_confidence: Confidence after rephrase

        Returns:
            Escalation decision
        """
        # Use rephrase confidence if available
        effective_confidence = rephrase_confidence if rephrase_confidence is not None else confidence

        # Check for immediate escalation (confidence < threshold)
        if effective_confidence < self.immediate_escalation_threshold:
            logger.warning(f"Immediate escalation: confidence {effective_confidence:.2f} < {self.immediate_escalation_threshold}")
            return EscalationDecision(
                should_escalate=True,
                reason=EscalationReason.LOW_CONFIDENCE,
                confidence_score=effective_confidence,
                rephrase_attempted=rephrase_attempted,
                rephrase_confidence=rephrase_confidence,
                low_confidence_count=low_confidence_count + 1,
                message="I'm not confident I can provide the best answer. Let me connect you with a human agent who can help better.",
                is_vip=self.is_vip,
                customer_type=self.customer_type,
                escalation_payload={"agent_team": self.get_agent_team()},
            )

        # Check for rephrase and escalate (threshold_low ≤ confidence < min_threshold)
        if self.rephrase_threshold_low <= effective_confidence < self.min_confidence_threshold:
            if not rephrase_attempted:
                # Try rephrase first
                logger.info(f"Rephrase recommended: confidence {effective_confidence:.2f} in range [{self.rephrase_threshold_low}, {self.min_confidence_threshold})")
                return EscalationDecision(
                    should_escalate=False,
                    reason=None,
                    confidence_score=effective_confidence,
                    rephrase_attempted=False,
                    rephrase_confidence=None,
                    low_confidence_count=low_confidence_count + 1,
                    message="",
                    is_vip=self.is_vip,
                    customer_type=self.customer_type,
                )
            else:
                # Rephrase already attempted, escalate
                logger.warning(f"Escalation after rephrase: confidence {effective_confidence:.2f} still below threshold")
                return EscalationDecision(
                    should_escalate=True,
                    reason=EscalationReason.REPHRASE_FAILED,
                    confidence_score=effective_confidence,
                    rephrase_attempted=True,
                    rephrase_confidence=rephrase_confidence,
                    low_confidence_count=low_confidence_count + 1,
                    message="I've tried to rephrase my response but I'm still not confident. Let me connect you with a human agent.",
                    is_vip=self.is_vip,
                    customer_type=self.customer_type,
                    escalation_payload={"agent_team": self.get_agent_team()},
                )

        # Check for consecutive low-confidence
        if low_confidence_count >= self.consecutive_low_confidence_limit:
            logger.warning(f"Escalation due to consecutive low confidence: {low_confidence_count} messages")
            return EscalationDecision(
                should_escalate=True,
                reason=EscalationReason.CONSECUTIVE_LOW_CONFIDENCE,
                confidence_score=effective_confidence,
                rephrase_attempted=rephrase_attempted,
                rephrase_confidence=rephrase_confidence,
                low_confidence_count=low_confidence_count,
                message="I've had difficulty providing confident answers on this topic. Let me connect you with a human agent.",
                is_vip=self.is_vip,
                customer_type=self.customer_type,
                escalation_payload={"agent_team": self.get_agent_team()},
            )

        # Confidence is acceptable
        logger.info(f"Confidence acceptable: {effective_confidence:.2f} >= {self.min_confidence_threshold}")
        return EscalationDecision(
            should_escalate=False,
            reason=None,
            confidence_score=effective_confidence,
            rephrase_attempted=rephrase_attempted,
            rephrase_confidence=rephrase_confidence,
            low_confidence_count=0,  # Reset count on success
            message="",
            is_vip=self.is_vip,
            customer_type=self.customer_type,
            escalation_payload={"agent_team": self.get_agent_team()},
        )

    def should_rephrase(self, confidence: float) -> bool:
        """
        Determine if rephrase should be attempted.

        Args:
            confidence: AI confidence score

        Returns:
            True if rephrase should be attempted
        """
        return self.rephrase_threshold_low <= confidence < self.min_confidence_threshold

    def log_low_confidence_query(
        self,
        query_id: str,
        conversation_id: str,
        user_id: str,
        query: str,
        confidence_score: float,
        rephrase_attempted: bool = False,
        rephrase_confidence: Optional[float] = None,
        escalated: bool = False,
        escalation_reason: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> LowConfidenceQuery:
        """
        Log low-confidence query for model improvement.

        Args:
            query_id: Unique query ID
            conversation_id: Conversation ID
            user_id: User ID
            query: Original user query
            confidence_score: AI confidence score
            rephrase_attempted: Whether rephrase was attempted
            rephrase_confidence: Confidence after rephrase
            escalated: Whether query was escalated
            escalation_reason: Reason for escalation
            context: Additional context

        Returns:
            Low confidence query record
        """
        low_confidence_query = LowConfidenceQuery(
            query_id=query_id,
            conversation_id=conversation_id,
            user_id=user_id,
            query=query,
            confidence_score=confidence_score,
            rephrase_attempted=rephrase_attempted,
            rephrase_confidence=rephrase_confidence,
            escalated=escalated,
            escalation_reason=escalation_reason,
            context=context or {},
        )

        # Log the query for analysis
        logger.info(
            f"Low confidence query logged - ID: {query_id}, "
            f"Confidence: {confidence_score:.2f}, "
            f"Rephrase: {rephrase_attempted}, "
            f"Escalated: {escalated}, "
            f"Reason: {escalation_reason}"
        )

        # TODO: Store in database for model improvement analysis
        # This would typically be stored in a dedicated table for ML team review

        return low_confidence_query

    def reset_low_confidence_count(self) -> int:
        """
        Reset low confidence count.

        Returns:
            Reset count (0)
        """
        return 0

    def calculate_message_similarity(self, message1: str, message2: str) -> float:
        """
        Calculate similarity between two messages using sequence matching.

        Args:
            message1: First message
            message2: Second message

        Returns:
            Similarity score between 0 and 1
        """
        if not message1 or not message2:
            return 0.0

        # Normalize messages (lowercase, strip whitespace)
        msg1_normalized = message1.lower().strip()
        msg2_normalized = message2.lower().strip()

        # Use difflib's SequenceMatcher for similarity
        similarity = difflib.SequenceMatcher(None, msg1_normalized, msg2_normalized).ratio()

        return similarity

    def is_failed_attempt(
        self,
        current_message: str,
        previous_messages: list[str],
        last_ai_response: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Determine if current message is a failed attempt (same/similar to previous message).

        Args:
            current_message: Current user message
            previous_messages: List of previous messages
            last_ai_response: Last AI response to user

        Returns:
            Tuple of (is_failed_attempt, reason)
        """
        if not previous_messages:
            return False, ""

        # Check similarity with most recent previous message
        most_recent_message = previous_messages[-1]
        similarity = self.calculate_message_similarity(current_message, most_recent_message)

        if similarity >= self.message_similarity_threshold:
            reason = f"Message similarity {similarity:.2f} >= threshold {self.message_similarity_threshold}"
            logger.info(f"Failed attempt detected: {reason}")
            return True, reason

        # Check similarity with any previous message (last 5 messages)
        for prev_msg in reversed(previous_messages[-5:]):
            if prev_msg == most_recent_message:
                continue  # Skip the most recent as we already checked it
            similarity = self.calculate_message_similarity(current_message, prev_msg)
            if similarity >= self.message_similarity_threshold:
                reason = f"Message similarity {similarity:.2f} with earlier message >= threshold {self.message_similarity_threshold}"
                logger.info(f"Failed attempt detected: {reason}")
                return True, reason

        return False, ""

    def evaluate_failed_attempts(
        self,
        failed_attempt_count: int,
        attempt_reasons: list[str],
    ) -> EscalationDecision:
        """
        Evaluate failed attempts and make escalation decision.

        Args:
            failed_attempt_count: Count of failed attempts
            attempt_reasons: List of reasons for failed attempts

        Returns:
            Escalation decision
        """
        if failed_attempt_count >= self.failed_attempt_limit:
            logger.warning(f"Escalation due to failed attempts: {failed_attempt_count} >= {self.failed_attempt_limit}")
            escalation_payload = {
                "failed_attempt_count": failed_attempt_count,
                "attempt_reasons": attempt_reasons,
                "limit_reached": True,
                "is_vip": self.is_vip,
                "customer_type": self.customer_type,
                "agent_team": self.get_agent_team(),
            }
            return EscalationDecision(
                should_escalate=True,
                reason=EscalationReason.FAILED_ATTEMPTS,
                confidence_score=0.0,  # Not applicable for failed attempts
                rephrase_attempted=False,
                rephrase_confidence=None,
                low_confidence_count=0,
                failed_attempt_count=failed_attempt_count,
                message=f"I notice we've been going in circles. Let me connect you with a human agent who can help resolve this issue.",
                escalation_payload=escalation_payload,
                is_vip=self.is_vip,
                customer_type=self.customer_type,
            )

        # Not yet at limit
        return EscalationDecision(
            should_escalate=False,
            reason=None,
            confidence_score=0.0,
            rephrase_attempted=False,
            rephrase_confidence=None,
            low_confidence_count=0,
            failed_attempt_count=failed_attempt_count,
            message="",
            escalation_payload={
                "failed_attempt_count": failed_attempt_count,
                "attempt_reasons": attempt_reasons,
                "limit_reached": False,
                "is_vip": self.is_vip,
                "customer_type": self.customer_type,
                "agent_team": self.get_agent_team(),
            },
            is_vip=self.is_vip,
            customer_type=self.customer_type,
        )

    def reset_failed_attempt_count(self) -> int:
        """
        Reset failed attempt count after successful resolution.

        Returns:
            Reset count (0)
        """
        logger.info("Resetting failed attempt count after successful resolution")
        return 0

    def evaluate_negative_sentiment(
        self,
        sentiment: Optional[str],
    ) -> Optional[EscalationDecision]:
        """
        Evaluate negative sentiment for VIP customers.

        VIP customers get escalated for any negative sentiment.

        Args:
            sentiment: Sentiment value (negative, neutral, positive)

        Returns:
            Escalation decision if VIP and negative sentiment, None otherwise
        """
        if not self.is_vip:
            return None

        if sentiment and sentiment.lower() == "negative":
            logger.warning(f"VIP customer with negative sentiment: {sentiment}")
            escalation_payload = {
                "sentiment": sentiment,
                "is_vip": self.is_vip,
                "customer_type": self.customer_type,
                "reason": "negative_sentiment",
                "agent_team": self.get_agent_team(),
            }
            return EscalationDecision(
                should_escalate=True,
                reason=EscalationReason.VIP_CUSTOMER,
                confidence_score=0.0,  # Not applicable for sentiment-based escalation
                rephrase_attempted=False,
                rephrase_confidence=None,
                low_confidence_count=0,
                failed_attempt_count=0,
                message="I notice you're experiencing some frustration. Let me connect you with our dedicated VIP support team right away.",
                escalation_payload=escalation_payload,
                is_vip=self.is_vip,
                customer_type=self.customer_type,
            )

        return None
