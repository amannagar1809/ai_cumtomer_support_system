"""CRM ticket fetcher for fetching open tickets from CRM."""

import json
import logging
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional

from app.core.redis import get_redis_client
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_TTL_SECONDS = 1800  # 30 minutes TTL (shorter for tickets)
CACHE_KEY_PREFIX = "crm_tickets:"


class CRMTicketStatus(str, Enum):
    """CRM ticket status."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ON_HOLD = "on_hold"


class CRMTicketPriority(str, Enum):
    """CRM ticket priority."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class CRMTicket(BaseModel):
    """CRM ticket model."""

    ticket_id: str = Field(description="Unique ticket ID in CRM")
    subject: str = Field(description="Ticket subject")
    description: str = Field(description="Ticket description")
    status: CRMTicketStatus = Field(description="Ticket status")
    priority: CRMTicketPriority = Field(description="Ticket priority")
    category: Optional[str] = Field(default=None, description="Ticket category")
    contact_id: str = Field(description="Associated contact ID")
    account_id: Optional[str] = Field(default=None, description="Associated account ID")
    created_date: datetime = Field(description="Ticket creation date")
    last_update: datetime = Field(description="Last update date")
    assigned_to: Optional[str] = Field(default=None, description="Assigned agent ID")
    resolved_at: Optional[datetime] = Field(default=None, description="Resolution date")
    internal_ticket_id: Optional[str] = Field(default=None, description="Cross-referenced internal ticket ID")
    is_duplicate: bool = Field(default=False, description="Whether ticket is duplicate of internal ticket")
    raw_crm_data: dict[str, Any] = Field(default_factory=dict, description="Raw CRM data")


class CRMTicketSummary(BaseModel):
    """CRM tickets summary."""

    customer_id: str = Field(description="Customer ID")
    total_tickets: int = Field(description="Total number of tickets")
    open_tickets: int = Field(description="Number of open tickets")
    in_progress_tickets: int = Field(description="Number of in-progress tickets")
    pending_tickets: int = Field(description="Number of pending tickets")
    high_priority_tickets: int = Field(description="Number of high/urgent/critical priority tickets")
    tickets: list[CRMTicket] = Field(default_factory=list, description="List of tickets")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Last update timestamp")


class CRMTicketFetcher:
    """CRM ticket fetcher for open tickets."""

    def __init__(self, cache_ttl_seconds: int = CACHE_TTL_SECONDS):
        """
        Initialize CRM ticket fetcher.

        Args:
            cache_ttl_seconds: Cache TTL in seconds
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        self.redis_client = None

    async def _get_redis_client(self):
        """Get Redis client."""
        if self.redis_client is None:
            self.redis_client = get_redis_client()
        return self.redis_client

    def _generate_cache_key(self, customer_id: str) -> str:
        """
        Generate cache key for CRM tickets.

        Args:
            customer_id: Customer ID

        Returns:
            Cache key
        """
        return f"{CACHE_KEY_PREFIX}{customer_id}"

    async def _cache_tickets(self, customer_id: str, summary: CRMTicketSummary) -> None:
        """
        Cache CRM tickets in Redis.

        Args:
            customer_id: Customer ID
            summary: CRM tickets summary
        """
        try:
            redis = await self._get_redis_client()
            cache_key = self._generate_cache_key(customer_id)
            summary_json = summary.model_dump_json()
            await redis.setex(cache_key, self.cache_ttl_seconds, summary_json)
            logger.info(f"Cached CRM tickets for customer: {customer_id}")
        except Exception as e:
            logger.warning(f"Failed to cache CRM tickets: {e}")

    async def _get_cached_tickets(self, customer_id: str) -> Optional[CRMTicketSummary]:
        """
        Get cached CRM tickets from Redis.

        Args:
            customer_id: Customer ID

        Returns:
            Cached CRM tickets summary or None
        """
        try:
            redis = await self._get_redis_client()
            cache_key = self._generate_cache_key(customer_id)
            summary_json = await redis.get(cache_key)

            if summary_json:
                summary_data = json.loads(summary_json)
                summary = CRMTicketSummary(**summary_data)
                logger.info(f"Retrieved cached CRM tickets for customer: {customer_id}")
                return summary

            return None
        except Exception as e:
            logger.warning(f"Failed to retrieve cached CRM tickets: {e}")
            return None

    async def _invalidate_cache(self, customer_id: str) -> None:
        """
        Invalidate cached CRM tickets.

        Args:
            customer_id: Customer ID
        """
        try:
            redis = await self._get_redis_client()
            cache_key = self._generate_cache_key(customer_id)
            await redis.delete(cache_key)
            logger.info(f"Invalidated CRM tickets cache for customer: {customer_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")

    def _map_crm_ticket(self, crm_data: dict[str, Any]) -> CRMTicket:
        """
        Map CRM ticket data to internal model.

        Args:
            crm_data: Raw CRM ticket data

        Returns:
            CRM ticket model
        """
        # Extract ticket fields
        ticket_id = crm_data.get("id", crm_data.get("ticket_id", "unknown"))
        subject = crm_data.get("subject", crm_data.get("title", "No Subject"))
        description = crm_data.get("description", crm_data.get("details", ""))

        # Map status
        status_str = crm_data.get("status", "open").lower()
        status = CRMTicketStatus(status_str) if status_str in [e.value for e in CRMTicketStatus] else CRMTicketStatus.OPEN

        # Map priority
        priority_str = crm_data.get("priority", crm_data.get("severity", "medium")).lower()
        priority = CRMTicketPriority(priority_str) if priority_str in [e.value for e in CRMTicketPriority] else CRMTicketPriority.MEDIUM

        category = crm_data.get("category", crm_data.get("type", None))
        contact_id = crm_data.get("contact_id", crm_data.get("customer_id", "unknown"))
        account_id = crm_data.get("account_id", crm_data.get("company_id", None))

        # Parse dates
        created_date_str = crm_data.get("created_at", crm_data.get("createddate", ""))
        if created_date_str:
            try:
                if isinstance(created_date_str, str):
                    created_date = datetime.fromisoformat(created_date_str.replace("Z", "+00:00"))
                else:
                    created_date = created_date_str
            except Exception:
                created_date = datetime.now(UTC)
        else:
            created_date = datetime.now(UTC)

        last_update_str = crm_data.get("updated_at", crm_data.get("lastmodifieddate", ""))
        if last_update_str:
            try:
                if isinstance(last_update_str, str):
                    last_update = datetime.fromisoformat(last_update_str.replace("Z", "+00:00"))
                else:
                    last_update = last_update_str
            except Exception:
                last_update = created_date
        else:
            last_update = created_date

        assigned_to = crm_data.get("assigned_to", crm_data.get("ownerid", None))

        resolved_at_str = crm_data.get("resolved_at", crm_data.get("closeddate", None))
        if resolved_at_str:
            try:
                if isinstance(resolved_at_str, str):
                    resolved_at = datetime.fromisoformat(resolved_at_str.replace("Z", "+00:00"))
                else:
                    resolved_at = resolved_at_str
            except Exception:
                resolved_at = None
        else:
            resolved_at = None

        ticket = CRMTicket(
            ticket_id=ticket_id,
            subject=subject,
            description=description,
            status=status,
            priority=priority,
            category=category,
            contact_id=contact_id,
            account_id=account_id,
            created_date=created_date,
            last_update=last_update,
            assigned_to=assigned_to,
            resolved_at=resolved_at,
            raw_crm_data=crm_data,
        )

        return ticket

    def _calculate_summary(self, tickets: list[CRMTicket], customer_id: str) -> CRMTicketSummary:
        """
        Calculate CRM tickets summary.

        Args:
            tickets: List of CRM tickets
            customer_id: Customer ID

        Returns:
            CRM tickets summary
        """
        total_tickets = len(tickets)
        open_tickets = sum(1 for t in tickets if t.status == CRMTicketStatus.OPEN)
        in_progress_tickets = sum(1 for t in tickets if t.status == CRMTicketStatus.IN_PROGRESS)
        pending_tickets = sum(1 for t in tickets if t.status == CRMTicketStatus.PENDING)
        high_priority_tickets = sum(
            1 for t in tickets if t.priority in [CRMTicketPriority.HIGH, CRMTicketPriority.URGENT, CRMTicketPriority.CRITICAL]
        )

        summary = CRMTicketSummary(
            customer_id=customer_id,
            total_tickets=total_tickets,
            open_tickets=open_tickets,
            in_progress_tickets=in_progress_tickets,
            pending_tickets=pending_tickets,
            high_priority_tickets=high_priority_tickets,
            tickets=tickets,
        )

        return summary

    async def _cross_reference_internal_tickets(
        self,
        crm_tickets: list[CRMTicket],
        internal_tickets: list[dict[str, Any]],
    ) -> list[CRMTicket]:
        """
        Cross-reference CRM tickets with internal ticket system.

        Args:
            crm_tickets: List of CRM tickets
            internal_tickets: List of internal tickets

        Returns:
            Updated CRM tickets with internal ticket references
        """
        # Create mapping of internal tickets by subject/description similarity
        internal_ticket_map = {}
        for internal_ticket in internal_tickets:
            subject = internal_ticket.get("subject", "").lower()
            description = internal_ticket.get("description", "").lower()
            internal_ticket_map[subject] = internal_ticket.get("id")
            internal_ticket_map[description] = internal_ticket.get("id")

        # Cross-reference CRM tickets
        for crm_ticket in crm_tickets:
            crm_subject = crm_ticket.subject.lower()
            crm_description = crm_ticket.description.lower()

            # Check for matching internal ticket
            if crm_subject in internal_ticket_map:
                crm_ticket.internal_ticket_id = internal_ticket_map[crm_subject]
                crm_ticket.is_duplicate = True
            elif crm_description in internal_ticket_map:
                crm_ticket.internal_ticket_id = internal_ticket_map[crm_description]
                crm_ticket.is_duplicate = True

        logger.info(f"Cross-referenced {len(crm_tickets)} CRM tickets with internal system")
        return crm_tickets

    async def fetch_open_tickets(
        self,
        customer_id: str,
        contact_id: Optional[str] = None,
        crm_client: Optional[Any] = None,
        internal_tickets: Optional[list[dict[str, Any]]] = None,
    ) -> CRMTicketSummary:
        """
        Fetch open tickets for customer from CRM.

        Args:
            customer_id: Customer ID
            contact_id: CRM contact ID (optional)
            crm_client: CRM client (optional, for actual CRM query)
            internal_tickets: Internal tickets for cross-referencing (optional)

        Returns:
            CRM tickets summary
        """
        # Check cache first
        cached_summary = await self._get_cached_tickets(customer_id)
        if cached_summary:
            return cached_summary

        # Fetch from CRM (placeholder - requires actual CRM client)
        if crm_client:
            # TODO: Implement actual CRM query for open tickets
            crm_tickets_data = []
            # crm_tickets_data = await crm_client.get_open_tickets(contact_id or customer_id)
        else:
            # Placeholder data for testing
            crm_tickets_data = [
                {
                    "id": "crm_001",
                    "subject": "Login issue",
                    "description": "Unable to login to account",
                    "status": "open",
                    "priority": "high",
                    "category": "technical",
                    "contact_id": contact_id or customer_id,
                    "created_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
                    "updated_at": (datetime.now(UTC) - timedelta(hours=6)).isoformat(),
                },
                {
                    "id": "crm_002",
                    "subject": "Billing question",
                    "description": "Question about recent charge",
                    "status": "in_progress",
                    "priority": "medium",
                    "category": "billing",
                    "contact_id": contact_id or customer_id,
                    "created_at": (datetime.now(UTC) - timedelta(days=5)).isoformat(),
                    "updated_at": (datetime.now(UTC) - timedelta(hours=12)).isoformat(),
                },
            ]

        # Map CRM data to tickets
        tickets = [self._map_crm_ticket(t) for t in crm_tickets_data]

        # Cross-reference with internal tickets if provided
        if internal_tickets:
            tickets = await self._cross_reference_internal_tickets(tickets, internal_tickets)

        # Calculate summary
        summary = self._calculate_summary(tickets, customer_id)

        # Cache the summary
        await self._cache_tickets(customer_id, summary)

        return summary

    def check_duplicate_ticket(
        self,
        subject: str,
        description: str,
        crm_tickets: list[CRMTicket],
    ) -> Optional[CRMTicket]:
        """
        Check if a ticket already exists in CRM to prevent duplicate creation.

        Args:
            subject: New ticket subject
            description: New ticket description
            crm_tickets: Existing CRM tickets

        Returns:
            Existing CRM ticket if duplicate found, None otherwise
        """
        subject_lower = subject.lower()
        description_lower = description.lower()

        for crm_ticket in crm_tickets:
            # Check subject similarity
            if subject_lower == crm_ticket.subject.lower():
                return crm_ticket

            # Check description similarity
            if description_lower == crm_ticket.description.lower():
                return crm_ticket

            # Check partial match (contains)
            if subject_lower in crm_ticket.subject.lower() or crm_ticket.subject.lower() in subject_lower:
                return crm_ticket

        return None

    def generate_existing_ticket_message(self, crm_tickets: list[CRMTicket]) -> str:
        """
        Generate message to inform customer about existing tickets.

        Args:
            crm_tickets: List of CRM tickets

        Returns:
            Message for customer
        """
        if not crm_tickets:
            return ""

        open_tickets = [t for t in crm_tickets if t.status in [CRMTicketStatus.OPEN, CRMTicketStatus.IN_PROGRESS]]

        if not open_tickets:
            return ""

        message_parts = ["I see you have the following existing ticket(s) in progress:"]
        for i, ticket in enumerate(open_tickets, 1):
            status_text = "Open" if ticket.status == CRMTicketStatus.OPEN else "In Progress"
            message_parts.append(
                f"{i}. {ticket.subject} (Status: {status_text}, Priority: {ticket.priority.value}, "
                f"Created: {ticket.created_date.strftime('%Y-%m-%d')})"
            )

        message_parts.append("Would you like me to provide an update on any of these tickets, or is this a new issue?")
        return "\n".join(message_parts)

    async def invalidate_tickets_cache(self, customer_id: str) -> None:
        """
        Invalidate CRM tickets cache.

        Args:
            customer_id: Customer ID
        """
        await self._invalidate_cache(customer_id)
