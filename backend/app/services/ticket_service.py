from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.ticket import Ticket, TicketStatus
from app.models.user import User
from app.schemas.queue import AnalyticsEvent
from app.schemas.ticket import ReopenTicketResponse, TicketListResponse, TicketSummary
from app.services.chat_session import anonymous_email
from app.services.message_queue import MessageQueueService
from app.services.ticket_events import TicketEventPublisher


class TicketServiceError(ValueError):
    pass


class TicketService:
    def __init__(self) -> None:
        self._events = TicketEventPublisher()
        self._queue = MessageQueueService()

    async def _get_user_by_anonymous_id(
        self,
        db: AsyncSession,
        anonymous_user_id: UUID,
    ) -> User | None:
        result = await db.execute(
            select(User).where(User.email == anonymous_email(anonymous_user_id))
        )
        return result.scalar_one_or_none()

    def _to_summary(self, ticket: Ticket) -> TicketSummary:
        return TicketSummary(
            ticket_id=ticket.id,
            status=ticket.status.value,
            priority=ticket.priority.value,
            category=ticket.category,
            created_at=ticket.created_at.replace(tzinfo=UTC)
            if ticket.created_at.tzinfo is None
            else ticket.created_at,
            resolved_at=(
                ticket.resolved_at.replace(tzinfo=UTC)
                if ticket.resolved_at and ticket.resolved_at.tzinfo is None
                else ticket.resolved_at
            ),
            conversation_id=ticket.conversation_id,
            can_reopen=ticket.status in (TicketStatus.closed, TicketStatus.resolved),
        )

    async def _get_owned_ticket(
        self,
        db: AsyncSession,
        ticket_id: UUID,
        anonymous_user_id: UUID,
    ) -> Ticket | None:
        user = await self._get_user_by_anonymous_id(db, anonymous_user_id)
        if user is None:
            return None

        stmt = (
            select(Ticket)
            .join(Conversation, Ticket.conversation_id == Conversation.id)
            .where(Ticket.id == ticket_id, Conversation.user_id == user.id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_user_tickets(
        self,
        db: AsyncSession,
        anonymous_user_id: UUID,
    ) -> TicketListResponse:
        user = await self._get_user_by_anonymous_id(db, anonymous_user_id)
        if user is None:
            return TicketListResponse(tickets=[], total=0)

        stmt = (
            select(Ticket)
            .join(Conversation, Ticket.conversation_id == Conversation.id)
            .where(Conversation.user_id == user.id)
            .order_by(desc(Ticket.created_at))
        )
        result = await db.execute(stmt)
        tickets = list(result.scalars().all())
        summaries = [self._to_summary(t) for t in tickets]
        return TicketListResponse(tickets=summaries, total=len(summaries))

    async def get_ticket(
        self,
        db: AsyncSession,
        ticket_id: UUID,
        anonymous_user_id: UUID,
    ) -> TicketSummary | None:
        ticket = await self._get_owned_ticket(db, ticket_id, anonymous_user_id)
        if ticket is None:
            return None
        return self._to_summary(ticket)

    async def reopen_ticket(
        self,
        db: AsyncSession,
        ticket_id: UUID,
        anonymous_user_id: UUID,
        reason: str,
    ) -> ReopenTicketResponse:
        ticket = await self._get_owned_ticket(db, ticket_id, anonymous_user_id)
        if ticket is None:
            raise TicketServiceError("Ticket not found")

        if ticket.status not in (TicketStatus.closed, TicketStatus.resolved):
            raise TicketServiceError(
                f"Only closed or resolved tickets can be reopened (current: {ticket.status.value})"
            )

        ticket.status = TicketStatus.open
        ticket.resolved_at = None
        await db.flush()
        await db.commit()

        summary = self._to_summary(ticket)
        await self._events.publish_status_change(
            anonymous_user_id=anonymous_user_id,
            ticket_id=ticket.id,
            status=summary.status,
            priority=summary.priority,
        )
        await self._queue.publish_analytics(
            AnalyticsEvent(
                event_type="ticket.reopened",
                conversation_id=str(ticket.conversation_id),
                properties={
                    "ticket_id": str(ticket.id),
                    "reason": reason,
                    "previous_status": TicketStatus.closed.value,
                },
            ),
            correlation_id=str(ticket.id),
        )

        return ReopenTicketResponse(
            ticket=summary,
            message="Ticket reopened successfully. Our team will follow up soon.",
        )

    async def notify_status_change(
        self,
        db: AsyncSession,
        ticket_id: UUID,
        *,
        new_status: TicketStatus,
    ) -> None:
        """Called when ticket status changes elsewhere; fans out to Redis subscribers."""
        ticket = await db.get(Ticket, ticket_id)
        if ticket is None:
            return

        conversation = await db.get(Conversation, ticket.conversation_id)
        if conversation is None:
            return

        user = await db.get(User, conversation.user_id)
        if user is None or not user.email.startswith("anon-"):
            return

        anonymous_id = UUID(user.email.removeprefix("anon-").removesuffix("@guest.local"))
        await self._events.publish_status_change(
            anonymous_user_id=anonymous_id,
            ticket_id=ticket.id,
            status=new_status.value,
            priority=ticket.priority.value,
        )
