"""Pending tickets queue service for managing auto-generated tickets pending human review."""

import logging
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PendingTicketStatus(str, Enum):
    """Status of pending ticket."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RejectionReason(str, Enum):
    """Reasons for rejecting a pending ticket."""

    NOT_AN_ISSUE = "not_an_issue"
    DUPLICATE = "duplicate"
    INCORRECT_DATA = "incorrect_data"
    LOW_CONFIDENCE = "low_confidence"
    RESOLVED_EXTERNALLY = "resolved_externally"
    OTHER = "other"


class PendingTicket(BaseModel):
    """Pending ticket awaiting human review."""

    ticket_id: str = Field(description="Unique pending ticket ID")
    conversation_id: str = Field(description="Original conversation ID")
    user_id: str = Field(description="User ID")
    issue_summary: str = Field(description="Issue summary")
    issue_description: str = Field(description="Issue description")
    priority: str = Field(description="Ticket priority")
    category: str = Field(description="Ticket category")
    affected_product: Optional[str] = Field(default=None, description="Affected product")
    steps_to_reproduce: Optional[str] = Field(default=None, description="Steps to reproduce")
    extraction_confidence: float = Field(description="Extraction confidence score")
    extraction_id: str = Field(description="Extraction ID")
    status: PendingTicketStatus = Field(default=PendingTicketStatus.PENDING, description="Ticket status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Creation timestamp")
    reviewed_at: Optional[datetime] = Field(default=None, description="Review timestamp")
    reviewed_by: Optional[str] = Field(default=None, description="Agent ID who reviewed")
    rejection_reason: Optional[RejectionReason] = Field(default=None, description="Rejection reason")
    rejection_notes: Optional[str] = Field(default=None, description="Additional rejection notes")
    edited_fields: list[str] = Field(default_factory=list, description="Fields edited by agent")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class PendingTicketsQueue:
    """Pending tickets queue for managing auto-generated tickets."""

    def __init__(self):
        """Initialize the pending tickets queue."""
        # In-memory storage (in production, use database)
        self.pending_tickets: dict[str, PendingTicket] = {}
        self.rejection_logs: list[dict[str, Any]] = []

    def add_pending_ticket(
        self,
        conversation_id: str,
        user_id: str,
        extracted_data: dict[str, Any],
        extraction_id: str,
        extraction_confidence: float,
        metadata: Optional[dict[str, Any]] = None,
    ) -> PendingTicket:
        """
        Add a ticket to the pending queue.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            extracted_data: Extracted ticket data
            extraction_id: Extraction ID
            extraction_confidence: Extraction confidence score
            metadata: Additional metadata

        Returns:
            Pending ticket
        """
        ticket_id = str(uuid.uuid4())

        ticket = PendingTicket(
            ticket_id=ticket_id,
            conversation_id=conversation_id,
            user_id=user_id,
            issue_summary=extracted_data.get("issue_summary", ""),
            issue_description=extracted_data.get("issue_description", ""),
            priority=extracted_data.get("priority", "medium"),
            category=extracted_data.get("category", "other"),
            affected_product=extracted_data.get("affected_product"),
            steps_to_reproduce=extracted_data.get("steps_to_reproduce"),
            extraction_confidence=extraction_confidence,
            extraction_id=extraction_id,
            status=PendingTicketStatus.PENDING,
            metadata=metadata or {},
        )

        self.pending_tickets[ticket_id] = ticket

        logger.info(
            f"Pending ticket added: {ticket_id}, "
            f"conversation: {conversation_id}, "
            f"confidence: {extraction_confidence:.2f}"
        )

        return ticket

    def get_pending_ticket(self, ticket_id: str) -> Optional[PendingTicket]:
        """
        Get a pending ticket by ID.

        Args:
            ticket_id: Ticket ID

        Returns:
            Pending ticket or None
        """
        return self.pending_tickets.get(ticket_id)

    def get_all_pending_tickets(self) -> list[PendingTicket]:
        """
        Get all pending tickets.

        Returns:
            List of pending tickets
        """
        return [ticket for ticket in self.pending_tickets.values() if ticket.status == PendingTicketStatus.PENDING]

    def get_pending_tickets_by_user(self, user_id: str) -> list[PendingTicket]:
        """
        Get pending tickets for a specific user.

        Args:
            user_id: User ID

        Returns:
            List of pending tickets
        """
        return [
            ticket for ticket in self.pending_tickets.values()
            if ticket.user_id == user_id and ticket.status == PendingTicketStatus.PENDING
        ]

    def edit_pending_ticket(
        self,
        ticket_id: str,
        edited_data: dict[str, Any],
        agent_id: str,
    ) -> Optional[PendingTicket]:
        """
        Edit a pending ticket.

        Args:
            ticket_id: Ticket ID
            edited_data: Edited ticket data
            agent_id: Agent ID

        Returns:
            Updated pending ticket or None
        """
        ticket = self.pending_tickets.get(ticket_id)
        if not ticket:
            logger.error(f"Pending ticket not found: {ticket_id}")
            return None

        if ticket.status != PendingTicketStatus.PENDING:
            logger.error(f"Cannot edit ticket with status: {ticket.status}")
            return None

        # Track edited fields
        edited_fields = []
        if "issue_summary" in edited_data and edited_data["issue_summary"] != ticket.issue_summary:
            ticket.issue_summary = edited_data["issue_summary"]
            edited_fields.append("issue_summary")
        if "issue_description" in edited_data and edited_data["issue_description"] != ticket.issue_description:
            ticket.issue_description = edited_data["issue_description"]
            edited_fields.append("issue_description")
        if "priority" in edited_data and edited_data["priority"] != ticket.priority:
            ticket.priority = edited_data["priority"]
            edited_fields.append("priority")
        if "category" in edited_data and edited_data["category"] != ticket.category:
            ticket.category = edited_data["category"]
            edited_fields.append("category")
        if "affected_product" in edited_data:
            ticket.affected_product = edited_data["affected_product"]
            edited_fields.append("affected_product")
        if "steps_to_reproduce" in edited_data:
            ticket.steps_to_reproduce = edited_data["steps_to_reproduce"]
            edited_fields.append("steps_to_reproduce")

        ticket.edited_fields = edited_fields
        ticket.reviewed_by = agent_id
        ticket.reviewed_at = datetime.now(UTC)

        logger.info(
            f"Pending ticket edited: {ticket_id}, "
            f"agent: {agent_id}, "
            f"edited_fields: {edited_fields}"
        )

        return ticket

    def approve_ticket(
        self,
        ticket_id: str,
        agent_id: str,
    ) -> Optional[PendingTicket]:
        """
        Approve a pending ticket and send to ticketing engine.

        Args:
            ticket_id: Ticket ID
            agent_id: Agent ID

        Returns:
            Approved ticket or None
        """
        ticket = self.pending_tickets.get(ticket_id)
        if not ticket:
            logger.error(f"Pending ticket not found: {ticket_id}")
            return None

        if ticket.status != PendingTicketStatus.PENDING:
            logger.error(f"Cannot approve ticket with status: {ticket.status}")
            return None

        ticket.status = PendingTicketStatus.APPROVED
        ticket.reviewed_by = agent_id
        ticket.reviewed_at = datetime.now(UTC)

        # Send to ticketing engine (placeholder)
        self._send_to_ticketing_engine(ticket)

        logger.info(
            f"Pending ticket approved: {ticket_id}, "
            f"agent: {agent_id}, "
            f"sent to ticketing engine"
        )

        return ticket

    def reject_ticket(
        self,
        ticket_id: str,
        agent_id: str,
        rejection_reason: RejectionReason,
        rejection_notes: Optional[str] = None,
    ) -> Optional[PendingTicket]:
        """
        Reject a pending ticket and log reason for AI improvement.

        Args:
            ticket_id: Ticket ID
            agent_id: Agent ID
            rejection_reason: Reason for rejection
            rejection_notes: Additional notes

        Returns:
            Rejected ticket or None
        """
        ticket = self.pending_tickets.get(ticket_id)
        if not ticket:
            logger.error(f"Pending ticket not found: {ticket_id}")
            return None

        if ticket.status != PendingTicketStatus.PENDING:
            logger.error(f"Cannot reject ticket with status: {ticket.status}")
            return None

        ticket.status = PendingTicketStatus.REJECTED
        ticket.reviewed_by = agent_id
        ticket.reviewed_at = datetime.now(UTC)
        ticket.rejection_reason = rejection_reason
        ticket.rejection_notes = rejection_notes

        # Log rejection for AI model improvement
        self._log_rejection(ticket, rejection_reason, rejection_notes)

        logger.info(
            f"Pending ticket rejected: {ticket_id}, "
            f"agent: {agent_id}, "
            f"reason: {rejection_reason.value}"
        )

        return ticket

    def _send_to_ticketing_engine(self, ticket: PendingTicket) -> None:
        """
        Send approved ticket to ticketing engine.

        Args:
            ticket: Approved ticket
        """
        # TODO: Implement actual ticketing engine integration
        # For now, log the action
        logger.info(
            f"Sending ticket to ticketing engine: {ticket.ticket_id}, "
            f"conversation: {ticket.conversation_id}, "
            f"priority: {ticket.priority}, "
            f"category: {ticket.category}"
        )

    def _log_rejection(
        self,
        ticket: PendingTicket,
        rejection_reason: RejectionReason,
        rejection_notes: Optional[str],
    ) -> None:
        """
        Log rejection for AI model improvement.

        Args:
            ticket: Rejected ticket
            rejection_reason: Reason for rejection
            rejection_notes: Additional notes
        """
        log_entry = {
            "log_id": str(uuid.uuid4()),
            "ticket_id": ticket.ticket_id,
            "conversation_id": ticket.conversation_id,
            "extraction_id": ticket.extraction_id,
            "extraction_confidence": ticket.extraction_confidence,
            "rejection_reason": rejection_reason.value,
            "rejection_notes": rejection_notes,
            "ticket_data": {
                "issue_summary": ticket.issue_summary,
                "issue_description": ticket.issue_description,
                "priority": ticket.priority,
                "category": ticket.category,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

        self.rejection_logs.append(log_entry)

        logger.info(f"Rejection logged for AI improvement: {log_entry}")

    def get_rejection_logs(self) -> list[dict[str, Any]]:
        """
        Get all rejection logs for AI model improvement.

        Returns:
            List of rejection logs
        """
        return self.rejection_logs.copy()

    def get_rejection_logs_by_reason(self, reason: RejectionReason) -> list[dict[str, Any]]:
        """
        Get rejection logs filtered by reason.

        Args:
            reason: Rejection reason

        Returns:
            List of rejection logs
        """
        return [log for log in self.rejection_logs if log["rejection_reason"] == reason.value]

    def get_ticket_statistics(self) -> dict[str, Any]:
        """
        Get statistics about pending tickets.

        Returns:
            Statistics dictionary
        """
        total = len(self.pending_tickets)
        pending = len([t for t in self.pending_tickets.values() if t.status == PendingTicketStatus.PENDING])
        approved = len([t for t in self.pending_tickets.values() if t.status == PendingTicketStatus.APPROVED])
        rejected = len([t for t in self.pending_tickets.values() if t.status == PendingTicketStatus.REJECTED])

        avg_confidence = 0.0
        if total > 0:
            avg_confidence = sum(t.extraction_confidence for t in self.pending_tickets.values()) / total

        return {
            "total_tickets": total,
            "pending_tickets": pending,
            "approved_tickets": approved,
            "rejected_tickets": rejected,
            "average_confidence": avg_confidence,
            "rejection_count": len(self.rejection_logs),
        }

    def format_for_dashboard(self, ticket: PendingTicket) -> dict[str, Any]:
        """
        Format pending ticket for dashboard display.

        Args:
            ticket: Pending ticket

        Returns:
            Formatted ticket data
        """
        return {
            "ticket_id": ticket.ticket_id,
            "conversation_id": ticket.conversation_id,
            "user_id": ticket.user_id,
            "ticket_data": {
                "issue_summary": ticket.issue_summary,
                "issue_description": ticket.issue_description,
                "priority": ticket.priority,
                "category": ticket.category,
                "affected_product": ticket.affected_product,
                "steps_to_reproduce": ticket.steps_to_reproduce,
            },
            "ai_metadata": {
                "extraction_confidence": ticket.extraction_confidence,
                "extraction_id": ticket.extraction_id,
                "needs_review": ticket.extraction_confidence < 0.7,
            },
            "status": ticket.status.value,
            "created_at": ticket.created_at.isoformat(),
            "reviewed_at": ticket.reviewed_at.isoformat() if ticket.reviewed_at else None,
            "reviewed_by": ticket.reviewed_by,
            "edited_fields": ticket.edited_fields,
        }
