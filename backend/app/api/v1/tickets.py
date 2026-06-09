import asyncio
import json
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis_client
from app.schemas.ticket import (
    ReopenTicketRequest,
    ReopenTicketResponse,
    TicketListResponse,
    TicketSummary,
)
from app.services.ticket_events import ticket_updates_channel
from app.services.ticket_service import TicketService, TicketServiceError

router = APIRouter(prefix="/chat/tickets", tags=["tickets"])


@router.get("", response_model=TicketListResponse)
async def list_my_tickets(
    anonymous_user_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TicketListResponse:
    service = TicketService()
    return await service.list_user_tickets(db, anonymous_user_id)


@router.get("/events/stream")
async def ticket_status_stream(
    anonymous_user_id: UUID,
) -> StreamingResponse:
    """Server-Sent Events stream for real-time ticket status updates."""

    async def event_generator() -> AsyncGenerator[str, None]:
        redis = get_redis_client()
        pubsub = redis.pubsub()
        channel = ticket_updates_channel(anonymous_user_id)
        await pubsub.subscribe(channel)
        try:
            yield f"event: connected\ndata: {json.dumps({'channel': channel})}\n\n"
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message and message.get("type") == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    yield f"event: ticket.status_changed\ndata: {data}\n\n"
                else:
                    yield ": keepalive\n\n"
                    await asyncio.sleep(15)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{ticket_id}", response_model=TicketSummary)
async def get_ticket(
    ticket_id: UUID,
    anonymous_user_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TicketSummary:
    service = TicketService()
    ticket = await service.get_ticket(db, ticket_id, anonymous_user_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
    return ticket


@router.post("/{ticket_id}/reopen", response_model=ReopenTicketResponse)
async def reopen_ticket(
    ticket_id: UUID,
    body: ReopenTicketRequest,
    db: AsyncSession = Depends(get_db),
) -> ReopenTicketResponse:
    service = TicketService()
    try:
        return await service.reopen_ticket(
            db,
            ticket_id,
            body.anonymous_user_id,
            body.reason,
        )
    except TicketServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
