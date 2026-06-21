"""Ticket data extraction module for extracting structured ticket data from conversations."""

import logging
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Ticket extraction configuration
MAX_SUMMARY_LENGTH = 200  # Maximum characters for issue summary
REQUIRED_FIELDS = ["issue_summary", "issue_description", "priority", "category"]


class TicketPriority(str, Enum):
    """Ticket priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketCategory(str, Enum):
    """Ticket categories."""

    BILLING = "billing"
    TECHNICAL = "technical"
    PRODUCT = "product"
    ACCOUNT = "account"
    OTHER = "other"


class ExtractedTicketData(BaseModel):
    """Structured ticket data extracted from conversation."""

    issue_summary: str = Field(description="Issue summary (max 200 chars)")
    issue_description: str = Field(description="Full issue description from conversation")
    priority: TicketPriority = Field(description="Ticket priority")
    category: TicketCategory = Field(description="Ticket category")
    affected_product: Optional[str] = Field(default=None, description="Affected product")
    steps_to_reproduce: Optional[str] = Field(default=None, description="Steps to reproduce the issue")
    conversation_id: str = Field(description="Original conversation ID")
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Extraction timestamp")
    extraction_confidence: float = Field(description="Extraction confidence score (0-1)")
    is_valid: bool = Field(default=True, description="Whether extracted data is valid")
    validation_errors: list[str] = Field(default_factory=list, description="Validation errors")
    needs_human_review: bool = Field(default=False, description="Whether human review is needed")

    @field_validator("issue_summary")
    @classmethod
    def validate_summary_length(cls, v: str) -> str:
        """Validate summary length."""
        if len(v) > MAX_SUMMARY_LENGTH:
            logger.warning(f"Issue summary too long ({len(v)} chars), truncating to {MAX_SUMMARY_LENGTH}")
            return v[:MAX_SUMMARY_LENGTH]
        return v

    @field_validator("extraction_confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate confidence score."""
        if not 0 <= v <= 1:
            raise ValueError("Confidence must be between 0 and 1")
        return v


class TicketExtractionResult(BaseModel):
    """Result of ticket extraction."""

    extraction_id: str = Field(description="Unique extraction ID")
    ticket_data: ExtractedTicketData = Field(description="Extracted ticket data")
    conversation_history: list[dict[str, Any]] = Field(default_factory=list, description="Conversation history used")
    extraction_method: str = Field(description="Method used for extraction")
    human_edited: bool = Field(default=False, description="Whether data was edited by human")
    human_editor_id: Optional[str] = Field(default=None, description="Human agent ID who edited")
    edited_at: Optional[datetime] = Field(default=None, description="When human edited the data")


class TicketExtractor:
    """Ticket data extractor for extracting structured ticket data from conversations."""

    def __init__(self):
        """Initialize the ticket extractor."""
        pass

    def _validate_ticket_data(self, ticket_data: ExtractedTicketData) -> tuple[bool, list[str]]:
        """
        Validate extracted ticket data completeness.

        Args:
            ticket_data: Extracted ticket data

        Returns:
            Tuple of (is_valid, validation_errors)
        """
        errors = []

        # Check required fields
        if not ticket_data.issue_summary or len(ticket_data.issue_summary.strip()) == 0:
            errors.append("issue_summary is required")

        if not ticket_data.issue_description or len(ticket_data.issue_description.strip()) == 0:
            errors.append("issue_description is required")

        if not ticket_data.priority:
            errors.append("priority is required")

        if not ticket_data.category:
            errors.append("category is required")

        # Check confidence threshold
        if ticket_data.extraction_confidence < 0.5:
            errors.append(f"Low extraction confidence: {ticket_data.extraction_confidence}")

        # Check if human review needed
        if ticket_data.extraction_confidence < 0.7:
            ticket_data.needs_human_review = True

        is_valid = len(errors) == 0
        ticket_data.is_valid = is_valid
        ticket_data.validation_errors = errors

        return is_valid, errors

    def _extract_with_llm(
        self,
        conversation_history: list[dict[str, Any]],
        conversation_id: str,
    ) -> ExtractedTicketData:
        """
        Extract ticket data using LLM (placeholder implementation).

        Args:
            conversation_history: Conversation history
            conversation_id: Conversation ID

        Returns:
            Extracted ticket data
        """
        # TODO: Implement actual LLM-based extraction
        # For now, use keyword-based extraction as placeholder

        # Combine all messages
        all_messages = " ".join([msg.get("content", "") for msg in conversation_history])

        # Extract summary (first 200 chars of last message)
        last_message = conversation_history[-1].get("content", "") if conversation_history else ""
        summary = last_message[:MAX_SUMMARY_LENGTH]

        # Extract description (last 3 messages combined)
        recent_messages = conversation_history[-3:] if len(conversation_history) >= 3 else conversation_history
        description = " ".join([msg.get("content", "") for msg in recent_messages])

        # Determine priority based on keywords
        message_lower = all_messages.lower()
        if any(word in message_lower for word in ["urgent", "emergency", "critical", "asap"]):
            priority = TicketPriority.URGENT
        elif any(word in message_lower for word in ["high", "important", "priority"]):
            priority = TicketPriority.HIGH
        elif any(word in message_lower for word in ["low", "minor", "trivial"]):
            priority = TicketPriority.LOW
        else:
            priority = TicketPriority.MEDIUM

        # Determine category based on keywords
        if any(word in message_lower for word in ["billing", "payment", "refund", "charge", "invoice"]):
            category = TicketCategory.BILLING
        elif any(word in message_lower for word in ["technical", "bug", "error", "crash", "broken"]):
            category = TicketCategory.TECHNICAL
        elif any(word in message_lower for word in ["product", "feature", "upgrade", "version"]):
            category = TicketCategory.PRODUCT
        elif any(word in message_lower for word in ["account", "login", "password", "profile"]):
            category = TicketCategory.ACCOUNT
        else:
            category = TicketCategory.OTHER

        # Extract affected product (placeholder)
        affected_product = None
        if "product" in message_lower:
            # Simple extraction - in production, use NER
            words = message_lower.split()
            for i, word in enumerate(words):
                if word == "product" and i + 1 < len(words):
                    affected_product = words[i + 1].capitalize()
                    break

        # Extract steps to reproduce (placeholder)
        steps_to_reproduce = None
        if "reproduce" in message_lower or "steps" in message_lower:
            # Simple extraction - in production, use more sophisticated NLP
            steps_to_reproduce = "Steps to reproduce extracted from conversation"

        return ExtractedTicketData(
            issue_summary=summary,
            issue_description=description,
            priority=priority,
            category=category,
            affected_product=affected_product,
            steps_to_reproduce=steps_to_reproduce,
            conversation_id=conversation_id,
            extraction_confidence=0.75,  # Placeholder confidence
        )

    def extract_ticket_data(
        self,
        conversation_history: list[dict[str, Any]],
        conversation_id: str,
        use_llm: bool = True,
    ) -> TicketExtractionResult:
        """
        Extract structured ticket data from conversation.

        Args:
            conversation_history: Conversation history
            conversation_id: Conversation ID
            use_llm: Whether to use LLM for extraction

        Returns:
            Ticket extraction result
        """
        extraction_id = str(uuid.uuid4())

        try:
            # Extract ticket data
            if use_llm:
                ticket_data = self._extract_with_llm(conversation_history, conversation_id)
                extraction_method = "llm"
            else:
                # Fallback to rule-based extraction
                ticket_data = self._extract_with_llm(conversation_history, conversation_id)
                extraction_method = "rule_based"

            # Validate extracted data
            is_valid, validation_errors = self._validate_ticket_data(ticket_data)

            # Create result
            result = TicketExtractionResult(
                extraction_id=extraction_id,
                ticket_data=ticket_data,
                conversation_history=conversation_history,
                extraction_method=extraction_method,
            )

            logger.info(
                f"Ticket data extracted: {extraction_id}, "
                f"valid={is_valid}, "
                f"confidence={ticket_data.extraction_confidence:.2f}, "
                f"needs_review={ticket_data.needs_human_review}"
            )

            return result

        except Exception as e:
            logger.error(f"Error extracting ticket data: {e}")
            raise

    def allow_human_edit(
        self,
        extraction_result: TicketExtractionResult,
        edited_data: dict[str, Any],
        human_agent_id: str,
    ) -> TicketExtractionResult:
        """
        Allow human agent to edit extracted ticket data before final creation.

        Args:
            extraction_result: Original extraction result
            edited_data: Edited ticket data
            human_agent_id: Human agent ID

        Returns:
            Updated extraction result with edited data
        """
        # Update ticket data with edits
        original_data = extraction_result.ticket_data

        # Create edited ticket data
        edited_ticket_data = ExtractedTicketData(
            issue_summary=edited_data.get("issue_summary", original_data.issue_summary),
            issue_description=edited_data.get("issue_description", original_data.issue_description),
            priority=TicketPriority(edited_data.get("priority", original_data.priority.value)),
            category=TicketCategory(edited_data.get("category", original_data.category.value)),
            affected_product=edited_data.get("affected_product", original_data.affected_product),
            steps_to_reproduce=edited_data.get("steps_to_reproduce", original_data.steps_to_reproduce),
            conversation_id=original_data.conversation_id,
            extracted_at=original_data.extracted_at,
            extraction_confidence=1.0,  # Human edit = 100% confidence
            is_valid=True,
            validation_errors=[],
            needs_human_review=False,
        )

        # Create updated result
        updated_result = TicketExtractionResult(
            extraction_id=extraction_result.extraction_id,
            ticket_data=edited_ticket_data,
            conversation_history=extraction_result.conversation_history,
            extraction_method=extraction_result.extraction_method,
            human_edited=True,
            human_editor_id=human_agent_id,
            edited_at=datetime.now(UTC),
        )

        logger.info(
            f"Ticket data edited by human agent {human_agent_id}: "
            f"extraction_id={extraction_result.extraction_id}"
        )

        return updated_result

    def format_for_display(self, extraction_result: TicketExtractionResult) -> dict[str, Any]:
        """
        Format extraction result for display to human agent.

        Args:
            extraction_result: Extraction result

        Returns:
            Formatted data for display
        """
        return {
            "extraction_id": extraction_result.extraction_id,
            "ticket_data": {
                "issue_summary": extraction_result.ticket_data.issue_summary,
                "issue_description": extraction_result.ticket_data.issue_description,
                "priority": extraction_result.ticket_data.priority.value,
                "category": extraction_result.ticket_data.category.value,
                "affected_product": extraction_result.ticket_data.affected_product,
                "steps_to_reproduce": extraction_result.ticket_data.steps_to_reproduce,
            },
            "metadata": {
                "conversation_id": extraction_result.ticket_data.conversation_id,
                "extraction_confidence": extraction_result.ticket_data.extraction_confidence,
                "is_valid": extraction_result.ticket_data.is_valid,
                "validation_errors": extraction_result.ticket_data.validation_errors,
                "needs_human_review": extraction_result.ticket_data.needs_human_review,
                "extraction_method": extraction_result.extraction_method,
                "human_edited": extraction_result.human_edited,
                "extracted_at": extraction_result.ticket_data.extracted_at.isoformat(),
            },
        }
