"""Ticket detection module for automatic ticket creation based on trigger conditions."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Ticket detection configuration
COOLDOWN_MINUTES = 5  # Cooldown period for same issue
LOW_CONFIDENCE_THRESHOLD = 0.60  # AI confidence threshold
MAX_AI_ATTEMPTS = 3  # Maximum AI attempts before triggering
MIN_REPEATED_ISSUES = 3  # Minimum times same issue must be mentioned
MIN_ANGRY_RESPONSES = 2  # Minimum angry responses before triggering


class TicketTriggerReason(str, Enum):
    """Reasons for triggering ticket creation."""

    LOW_CONFIDENCE = "low_confidence"
    EXPLICIT_REQUEST = "explicit_request"
    REFUND_REQUEST = "refund_request"
    COMPLAINT = "complaint"
    REPEATED_ISSUE = "repeated_issue"
    ANGRY_UNRESOLVED = "angry_unresolved"


class TicketDecision(str, Enum):
    """Ticket creation decision."""

    CREATE = "create"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"
    SKIP = "skip"


class TicketTrigger(BaseModel):
    """Ticket trigger details."""

    trigger_id: str = Field(description="Unique trigger ID")
    reason: TicketTriggerReason = Field(description="Reason for trigger")
    confidence: float = Field(description="Trigger confidence score")
    details: dict[str, Any] = Field(default_factory=dict, description="Trigger details")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Trigger timestamp")


class TicketAuditLog(BaseModel):
    """Audit log for ticket creation decisions."""

    log_id: str = Field(description="Unique log ID")
    conversation_id: str = Field(description="Conversation ID")
    user_id: str = Field(description="User ID")
    decision: TicketDecision = Field(description="Ticket creation decision")
    triggers: list[TicketTrigger] = Field(default_factory=list, description="Triggers detected")
    cooldown_active: bool = Field(default=False, description="Whether cooldown is active")
    user_cancelled: bool = Field(default=False, description="Whether user cancelled")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Log timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class TicketDetector:
    """Ticket detector for automatic ticket creation based on trigger conditions."""

    def __init__(
        self,
        cooldown_minutes: int = COOLDOWN_MINUTES,
        low_confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
        max_ai_attempts: int = MAX_AI_ATTEMPTS,
        min_repeated_issues: int = MIN_REPEATED_ISSUES,
        min_angry_responses: int = MIN_ANGRY_RESPONSES,
    ):
        """
        Initialize the ticket detector.

        Args:
            cooldown_minutes: Cooldown period for same issue in minutes
            low_confidence_threshold: AI confidence threshold
            max_ai_attempts: Maximum AI attempts before triggering
            min_repeated_issues: Minimum times same issue must be mentioned
            min_angry_responses: Minimum angry responses before triggering
        """
        self.cooldown_minutes = cooldown_minutes
        self.low_confidence_threshold = low_confidence_threshold
        self.max_ai_attempts = max_ai_attempts
        self.min_repeated_issues = min_repeated_issues
        self.min_angry_responses = min_angry_responses

        # Track cooldowns per conversation
        self.cooldowns: dict[str, datetime] = {}

        # Track issue mentions per conversation
        self.issue_mentions: dict[str, dict[str, int]] = {}

        # Track AI attempts per conversation
        self.ai_attempts: dict[str, int] = {}

        # Track angry responses per conversation
        self.angry_responses: dict[str, int] = {}

    def _is_cooldown_active(self, conversation_id: str) -> bool:
        """
        Check if cooldown is active for a conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            True if cooldown is active
        """
        if conversation_id not in self.cooldowns:
            return False

        cooldown_end = self.cooldowns[conversation_id]
        now = datetime.now(UTC)

        if now < cooldown_end:
            return True

        # Cooldown expired, remove it
        del self.cooldowns[conversation_id]
        return False

    def _set_cooldown(self, conversation_id: str) -> None:
        """
        Set cooldown for a conversation.

        Args:
            conversation_id: The conversation ID
        """
        cooldown_end = datetime.now(UTC) + timedelta(minutes=self.cooldown_minutes)
        self.cooldowns[conversation_id] = cooldown_end
        logger.info(f"Cooldown set for conversation {conversation_id} until {cooldown_end}")

    def _detect_explicit_request(self, message: str) -> bool:
        """
        Detect explicit ticket creation request.

        Args:
            message: The user message

        Returns:
            True if explicit request detected
        """
        message_lower = message.lower()
        explicit_phrases = [
            "create ticket",
            "talk to human",
            "escalate",
            "speak to agent",
            "human agent",
            "support ticket",
            "open ticket",
            "file ticket",
        ]

        for phrase in explicit_phrases:
            if phrase in message_lower:
                return True

        return False

    def _detect_refund_request(self, message: str) -> bool:
        """
        Detect refund request.

        Args:
            message: The user message

        Returns:
            True if refund request detected
        """
        message_lower = message.lower()
        refund_phrases = [
            "refund",
            "money back",
            "return",
            "chargeback",
            "get my money back",
            "refund my",
            "cancel and refund",
        ]

        for phrase in refund_phrases:
            if phrase in message_lower:
                return True

        return False

    def _detect_complaint(self, message: str) -> bool:
        """
        Detect complaint.

        Args:
            message: The user message

        Returns:
            True if complaint detected
        """
        message_lower = message.lower()
        complaint_phrases = [
            "complaint",
            "unhappy",
            "dissatisfied",
            "terrible service",
            "horrible",
            "awful",
            "disappointed",
            "not working",
            "broken",
            "defective",
            "poor quality",
        ]

        for phrase in complaint_phrases:
            if phrase in message_lower:
                return True

        return False

    def _track_issue_mention(self, conversation_id: str, message: str) -> None:
        """
        Track issue mentions for repeated issue detection.

        Args:
            conversation_id: The conversation ID
            message: The user message
        """
        # Simple keyword extraction (placeholder for more sophisticated NLP)
        words = message.lower().split()
        keywords = [word for word in words if len(word) > 4]  # Filter short words

        if conversation_id not in self.issue_mentions:
            self.issue_mentions[conversation_id] = {}

        for keyword in keywords:
            self.issue_mentions[conversation_id][keyword] = (
                self.issue_mentions[conversation_id].get(keyword, 0) + 1
            )

    def _check_repeated_issue(self, conversation_id: str) -> bool:
        """
        Check if same issue mentioned multiple times.

        Args:
            conversation_id: The conversation ID

        Returns:
            True if issue mentioned >= min_repeated_issues times
        """
        if conversation_id not in self.issue_mentions:
            return False

        for keyword, count in self.issue_mentions[conversation_id].items():
            if count >= self.min_repeated_issues:
                logger.info(f"Repeated issue detected: '{keyword}' mentioned {count} times")
                return True

        return False

    def _track_ai_attempt(self, conversation_id: str) -> int:
        """
        Track AI response attempts.

        Args:
            conversation_id: The conversation ID

        Returns:
            Current attempt count
        """
        if conversation_id not in self.ai_attempts:
            self.ai_attempts[conversation_id] = 0

        self.ai_attempts[conversation_id] += 1
        return self.ai_attempts[conversation_id]

    def _track_angry_response(self, conversation_id: str) -> int:
        """
        Track angry responses.

        Args:
            conversation_id: The conversation ID

        Returns:
            Current angry response count
        """
        if conversation_id not in self.angry_responses:
            self.angry_responses[conversation_id] = 0

        self.angry_responses[conversation_id] += 1
        return self.angry_responses[conversation_id]

    def detect_triggers(
        self,
        conversation_id: str,
        user_id: str,
        message: str,
        ai_confidence: Optional[float] = None,
        sentiment_class: Optional[str] = None,
        ai_response_count: int = 0,
    ) -> list[TicketTrigger]:
        """
        Detect ticket creation triggers.

        Args:
            conversation_id: The conversation ID
            user_id: The user ID
            message: The user message
            ai_confidence: AI response confidence score
            sentiment_class: Sentiment class
            ai_response_count: Number of AI responses given

        Returns:
            List of detected triggers
        """
        triggers = []

        # Check cooldown
        if self._is_cooldown_active(conversation_id):
            logger.info(f"Cooldown active for conversation {conversation_id}, skipping trigger detection")
            return triggers

        # Track issue mentions
        self._track_issue_mention(conversation_id, message)

        # 1. Low confidence after multiple attempts
        if ai_confidence and ai_confidence < self.low_confidence_threshold:
            attempt_count = self._track_ai_attempt(conversation_id)
            if attempt_count >= self.max_ai_attempts:
                triggers.append(
                    TicketTrigger(
                        trigger_id=str(uuid.uuid4()),
                        reason=TicketTriggerReason.LOW_CONFIDENCE,
                        confidence=1.0 - ai_confidence,
                        details={
                            "ai_confidence": ai_confidence,
                            "attempts": attempt_count,
                        },
                    )
                )

        # 2. Explicit request
        if self._detect_explicit_request(message):
            triggers.append(
                TicketTrigger(
                    trigger_id=str(uuid.uuid4()),
                    reason=TicketTriggerReason.EXPLICIT_REQUEST,
                    confidence=1.0,
                    details={"phrase": message},
                )
            )

        # 3. Refund request
        if self._detect_refund_request(message):
            triggers.append(
                TicketTrigger(
                    trigger_id=str(uuid.uuid4()),
                    reason=TicketTriggerReason.REFUND_REQUEST,
                    confidence=0.9,
                    details={"phrase": message},
                )
            )

        # 4. Complaint
        if self._detect_complaint(message):
            triggers.append(
                TicketTrigger(
                    trigger_id=str(uuid.uuid4()),
                    reason=TicketTriggerReason.COMPLAINT,
                    confidence=0.85,
                    details={"phrase": message},
                )
            )

        # 5. Repeated issue
        if self._check_repeated_issue(conversation_id):
            triggers.append(
                TicketTrigger(
                    trigger_id=str(uuid.uuid4()),
                    reason=TicketTriggerReason.REPEATED_ISSUE,
                    confidence=0.8,
                    details={"issue_mentions": self.issue_mentions[conversation_id]},
                )
            )

        # 6. Angry and unresolved
        if sentiment_class == "angry":
            angry_count = self._track_angry_response(conversation_id)
            if angry_count >= self.min_angry_responses and ai_response_count >= 2:
                triggers.append(
                    TicketTrigger(
                        trigger_id=str(uuid.uuid4()),
                        reason=TicketTriggerReason.ANGRY_UNRESOLVED,
                        confidence=0.9,
                        details={
                            "angry_responses": angry_count,
                            "ai_responses": ai_response_count,
                        },
                    )
                )

        return triggers

    def check_user_cancellation(self, message: str) -> bool:
        """
        Check if user wants to cancel ticket creation.

        Args:
            message: The user message

        Returns:
            True if user wants to cancel
        """
        message_lower = message.lower()
        cancellation_phrases = [
            "no thanks",
            "i'm fine",
            "no need",
            "never mind",
            "forget it",
            "cancel that",
            "don't create",
            "not necessary",
        ]

        for phrase in cancellation_phrases:
            if phrase in message_lower:
                return True

        return False

    def make_decision(
        self,
        conversation_id: str,
        user_id: str,
        triggers: list[TicketTrigger],
        user_cancelled: bool = False,
    ) -> TicketDecision:
        """
        Make ticket creation decision.

        Args:
            conversation_id: The conversation ID
            user_id: The user ID
            triggers: Detected triggers
            user_cancelled: Whether user cancelled

        Returns:
            Ticket creation decision
        """
        # Check cooldown
        if self._is_cooldown_active(conversation_id):
            return TicketDecision.DEFERRED

        # Check user cancellation
        if user_cancelled:
            return TicketDecision.CANCELLED

        # Check if any triggers detected
        if not triggers:
            return TicketDecision.SKIP

        # Create ticket if triggers detected
        return TicketDecision.CREATE

    def log_decision(
        self,
        conversation_id: str,
        user_id: str,
        decision: TicketDecision,
        triggers: list[TicketTrigger],
        user_cancelled: bool = False,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TicketAuditLog:
        """
        Log ticket creation decision for audit.

        Args:
            conversation_id: The conversation ID
            user_id: The user ID
            decision: Ticket creation decision
            triggers: Detected triggers
            user_cancelled: Whether user cancelled
            metadata: Additional metadata

        Returns:
            Audit log entry
        """
        log = TicketAuditLog(
            log_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            user_id=user_id,
            decision=decision,
            triggers=triggers,
            cooldown_active=self._is_cooldown_active(conversation_id),
            user_cancelled=user_cancelled,
            metadata=metadata or {},
        )

        # Log to application logger
        log_data = {
            "log_id": log.log_id,
            "conversation_id": log.conversation_id,
            "user_id": log.user_id,
            "decision": log.decision.value,
            "triggers": [t.model_dump() for t in triggers],
            "cooldown_active": log.cooldown_active,
            "user_cancelled": log.user_cancelled,
            "timestamp": log.timestamp.isoformat(),
        }

        logger.info(f"Ticket decision audit: {log_data}")

        return log

    def reset_conversation(self, conversation_id: str) -> None:
        """
        Reset conversation state (for new conversations).

        Args:
            conversation_id: The conversation ID
        """
        if conversation_id in self.cooldowns:
            del self.cooldowns[conversation_id]
        if conversation_id in self.issue_mentions:
            del self.issue_mentions[conversation_id]
        if conversation_id in self.ai_attempts:
            del self.ai_attempts[conversation_id]
        if conversation_id in self.angry_responses:
            del self.angry_responses[conversation_id]

        logger.info(f"Reset conversation state for {conversation_id}")
