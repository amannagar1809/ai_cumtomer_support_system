"""Customer profile service for fetching and managing customer data."""

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.ticket import Ticket, TicketStatus
from app.models.user import User, CustomerType
from app.services.langgraph.context_cache import ContextCacheService

logger = logging.getLogger(__name__)

# Data privacy configuration
# Only fetch necessary fields to respect data privacy
CUSTOMER_PROFILE_FIELDS = ["id", "name", "customer_type", "created_at", "language"]
TICKET_FIELDS = ["id", "category", "status", "priority", "created_at", "resolved_at"]
MAX_PAST_TICKETS = 5
TICKET_STATUSES_TO_FETCH = [TicketStatus.resolved, TicketStatus.closed]


class CustomerTier(str, Enum):
    """Customer tier levels."""

    REGULAR = "regular"
    PREMIUM = "premium"
    VIP = "vip"


class PastTicket(BaseModel):
    """Past ticket information."""

    ticket_id: str = Field(description="Ticket ID")
    category: str = Field(description="Ticket category")
    status: str = Field(description="Ticket status")
    priority: str = Field(description="Ticket priority")
    created_at: datetime = Field(description="Ticket creation date")
    resolved_at: Optional[datetime] = Field(default=None, description="Ticket resolution date")


class CustomerProfile(BaseModel):
    """Customer profile information."""

    customer_id: str = Field(description="Customer ID")
    name: str = Field(description="Customer name")
    tier: CustomerTier = Field(description="Customer tier")
    join_date: datetime = Field(description="Customer join date")
    language: str = Field(description="Customer preferred language")
    is_vip: bool = Field(default=False, description="Whether customer is VIP")


class CRMData(BaseModel):
    """Additional CRM data (placeholder for future integration)."""

    purchases: list[dict[str, Any]] = Field(default_factory=list, description="Purchase history")
    support_history: dict[str, Any] = Field(default_factory=dict, description="Support history")
    last_purchase_date: Optional[datetime] = Field(default=None, description="Last purchase date")
    total_spend: float = Field(default=0.0, description="Total amount spent")
    loyalty_points: int = Field(default=0, description="Loyalty points")


class CustomerContext(BaseModel):
    """Complete customer context combining profile, tickets, and CRM data."""

    profile: Optional[CustomerProfile] = Field(default=None, description="Customer profile")
    past_tickets: list[PastTicket] = Field(default_factory=list, description="Past tickets")
    crm_data: Optional[CRMData] = Field(default=None, description="CRM data")
    is_priority_customer: bool = Field(default=False, description="Whether customer gets priority handling")
    data_privacy_compliant: bool = Field(default=True, description="Whether data fetch respects privacy")


class CustomerProfileService:
    """Service for fetching and managing customer profile data with caching."""

    def __init__(
        self,
        max_past_tickets: int = MAX_PAST_TICKETS,
        ticket_statuses: list[TicketStatus] = TICKET_STATUSES_TO_FETCH,
        enable_cache: bool = True,
    ):
        """
        Initialize the customer profile service.

        Args:
            max_past_tickets: Maximum number of past tickets to fetch
            ticket_statuses: Ticket statuses to fetch
            enable_cache: Whether to enable Redis caching
        """
        self.max_past_tickets = max_past_tickets
        self.ticket_statuses = ticket_statuses
        self.enable_cache = enable_cache
        self.cache_service = ContextCacheService() if enable_cache else None

    async def fetch_customer_profile(
        self,
        user_id: str,
    ) -> Optional[CustomerProfile]:
        """
        Fetch customer profile from PostgreSQL.

        Args:
            user_id: The user ID

        Returns:
            Customer profile or None if not found
        """
        import uuid

        try:
            # Convert user_id to UUID if it's a string
            user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

            async for db in get_db():
                # Query only necessary fields for data privacy
                query = select(
                    User.id,
                    User.name,
                    User.customer_type,
                    User.created_at,
                    User.language,
                ).where(User.id == user_uuid)

                result = await db.execute(query)
                user_data = result.first()

                if not user_data:
                    logger.warning(f"Customer profile not found for user_id: {user_id}")
                    return None

                # Map CustomerType to CustomerTier
                tier = CustomerTier(user_data.customer_type.value)
                is_vip = tier == CustomerTier.VIP

                profile = CustomerProfile(
                    customer_id=str(user_data.id),
                    name=user_data.name,
                    tier=tier,
                    join_date=user_data.created_at,
                    language=user_data.language,
                    is_vip=is_vip,
                )

                logger.info(f"Fetched customer profile for {user_id}: {profile.name} ({tier.value})")
                return profile

        except Exception as e:
            logger.error(f"Failed to fetch customer profile: {e}")
            return None

    async def fetch_past_tickets(
        self,
        conversation_id: str,
    ) -> list[PastTicket]:
        """
        Fetch past tickets for a conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            List of past tickets
        """
        import uuid

        try:
            # Convert conversation_id to UUID if it's a string
            conv_uuid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id

            async for db in get_db():
                # Query only necessary fields for data privacy
                query = (
                    select(
                        Ticket.id,
                        Ticket.category,
                        Ticket.status,
                        Ticket.priority,
                        Ticket.created_at,
                        Ticket.resolved_at,
                    )
                    .where(Ticket.conversation_id == conv_uuid)
                    .where(Ticket.status.in_(self.ticket_statuses))
                    .order_by(Ticket.created_at.desc())
                    .limit(self.max_past_tickets)
                )

                result = await db.execute(query)
                tickets = result.all()

                past_tickets = []
                for ticket in tickets:
                    past_ticket = PastTicket(
                        ticket_id=str(ticket.id),
                        category=ticket.category,
                        status=ticket.status.value,
                        priority=ticket.priority.value,
                        created_at=ticket.created_at,
                        resolved_at=ticket.resolved_at,
                    )
                    past_tickets.append(past_ticket)

                logger.info(f"Fetched {len(past_tickets)} past tickets for conversation {conversation_id}")
                return past_tickets

        except Exception as e:
            logger.error(f"Failed to fetch past tickets: {e}")
            return []

    async def fetch_crm_data(
        self,
        user_id: str,
    ) -> CRMData:
        """
        Fetch additional CRM data for a customer.

        Args:
            user_id: The user ID

        Returns:
            CRM data (placeholder for future integration)
        """
        # TODO: Implement actual CRM integration
        # For now, return empty CRM data as placeholder
        logger.info(f"CRM data fetch not yet implemented for user_id: {user_id}")

        return CRMData(
            purchases=[],
            support_history={},
            last_purchase_date=None,
            total_spend=0.0,
            loyalty_points=0,
        )

    def identify_vip_customer(
        self,
        profile: Optional[CustomerProfile],
        past_tickets: list[PastTicket],
    ) -> bool:
        """
        Identify VIP customers for priority handling.

        Args:
            profile: Customer profile
            past_tickets: Past tickets

        Returns:
            True if customer should get priority handling
        """
        if not profile:
            return False

        # VIP based on tier
        if profile.is_vip:
            return True

        # VIP based on ticket history (e.g., many resolved tickets)
        if len(past_tickets) >= 3:
            return True

        # VIP based on premium tier
        if profile.tier == CustomerTier.PREMIUM:
            return True

        return False

    async def build_customer_context(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
    ) -> CustomerContext:
        """
        Build complete customer context combining profile, tickets, and CRM data with caching.

        Args:
            user_id: The user ID
            conversation_id: The conversation ID (optional)

        Returns:
            Complete customer context
        """
        # Check cache first (cache-aside pattern)
        if self.enable_cache and self.cache_service:
            cached_context = await self.cache_service.get(user_id, "customer")
            if cached_context:
                logger.info(f"Customer context cache hit for {user_id}")
                return CustomerContext(**cached_context)

        # Fetch customer profile
        profile = await self.fetch_customer_profile(user_id)

        # Fetch past tickets if conversation_id provided
        past_tickets = []
        if conversation_id:
            past_tickets = await self.fetch_past_tickets(conversation_id)

        # Fetch CRM data
        crm_data = await self.fetch_crm_data(user_id)

        # Identify VIP customers
        is_priority = self.identify_vip_customer(profile, past_tickets)

        # Build context
        context = CustomerContext(
            profile=profile,
            past_tickets=past_tickets,
            crm_data=crm_data,
            is_priority_customer=is_priority,
            data_privacy_compliant=True,  # We only fetch necessary fields
        )

        # Cache the context
        if self.enable_cache and self.cache_service:
            await self.cache_service.set(user_id, context.model_dump(), "customer")
            logger.debug(f"Cached customer context for {user_id}")

        logger.info(
            f"Built customer context for {user_id}: "
            f"VIP={is_priority}, tickets={len(past_tickets)}, tier={profile.tier.value if profile else 'N/A'}"
        )

        return context

    async def invalidate_customer_cache(self, user_id: str) -> bool:
        """
        Invalidate customer cache (called on profile update).

        Args:
            user_id: The user ID

        Returns:
            True if successful, False otherwise
        """
        if self.enable_cache and self.cache_service:
            return await self.cache_service.invalidate(user_id, "customer")
        return False

    def format_context_for_personalization(
        self,
        context: CustomerContext,
    ) -> str:
        """
        Format customer context for personalization in responses.

        Args:
            context: Customer context

        Returns:
            Formatted context string
        """
        parts = []

        if context.profile:
            parts.append(f"Customer: {context.profile.name}")
            parts.append(f"Tier: {context.profile.tier.value}")
            parts.append(f"Language: {context.profile.language}")
            if context.profile.is_vip:
                parts.append("VIP Customer: Yes")

        if context.past_tickets:
            parts.append(f"\nPast Tickets ({len(context.past_tickets)}):")
            for ticket in context.past_tickets:
                parts.append(f"- {ticket.category} ({ticket.status})")

        if context.is_priority_customer:
            parts.append("\nPriority Handling: Enabled")

        return "\n".join(parts)
