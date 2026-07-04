from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TicketSummary(BaseModel):
    ticket_id: UUID
    status: str
    priority: str
    category: str
    created_at: datetime
    resolved_at: datetime | None = None
    conversation_id: UUID
    can_reopen: bool = False


class TicketListResponse(BaseModel):
    tickets: list[TicketSummary]
    total: int


class ReopenTicketRequest(BaseModel):
    anonymous_user_id: UUID
    reason: str = Field(min_length=3, max_length=500)


class ReopenTicketResponse(BaseModel):
    ticket: TicketSummary
    message: str


class TicketStatusEvent(BaseModel):
    ticket_id: UUID
    status: str
    priority: str
    updated_at: datetime
    event: str = "ticket.status_changed"
