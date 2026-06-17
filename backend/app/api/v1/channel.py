"""Channel connector API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.services.channel_router import ChannelRouter
from app.services.dead_letter_queue import DeadLetterQueue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["channels"])

# Initialize services
channel_router = ChannelRouter()
dead_letter_queue = DeadLetterQueue()


@router.post("/route/{channel}")
async def route_message(channel: str, raw_message: dict[str, Any]) -> dict[str, Any]:
    """
    Route a message through the unified channel connector.

    This endpoint provides a unified interface for all channels.
    """
    try:
        result = await channel_router.handle_message(channel, raw_message)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error routing message: {e}")
        raise HTTPException(status_code=500, detail="Failed to route message")


@router.get("/health")
async def get_channel_health() -> dict[str, Any]:
    """Get health status of all channel connectors."""
    return channel_router.get_all_health_status()


@router.get("/health/{channel}")
async def get_channel_health_status(channel: str) -> dict[str, Any]:
    """Get health status of a specific channel connector."""
    try:
        return channel_router.get_channel_health_status(channel)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dead-letter-queue")
async def get_dead_letter_queue_stats(channel: str | None = None) -> dict[str, Any]:
    """Get statistics for the dead-letter queue."""
    return await dead_letter_queue.get_queue_stats(channel)


@router.get("/dead-letter-queue/{channel}")
async def get_dead_letter_queue_messages(channel: str, limit: int = 10) -> list[dict[str, Any]]:
    """Get failed messages from the dead-letter queue for a channel."""
    return await dead_letter_queue.get_messages(channel, limit)


@router.post("/dead-letter-queue/{channel}/retry/{index}")
async def retry_dead_letter_message(channel: str, index: int) -> dict[str, Any]:
    """Retry a failed message from the dead-letter queue."""
    messages = await dead_letter_queue.get_messages(channel, limit=index + 1)
    if index >= len(messages):
        raise HTTPException(status_code=404, detail="Message not found in queue")

    entry = messages[index]
    success = await dead_letter_queue.retry_message(channel, entry)

    return {"success": success, "channel": channel, "index": index}


@router.delete("/dead-letter-queue/{channel}")
async def clear_dead_letter_queue(channel: str) -> dict[str, Any]:
    """Clear all messages from the dead-letter queue for a channel."""
    count = await dead_letter_queue.clear_queue(channel)
    return {"channel": channel, "messages_cleared": count}


@router.post("/dead-letter-queue/{channel}/purge")
async def purge_old_dead_letter_entries(
    channel: str, max_age_hours: int = 24
) -> dict[str, Any]:
    """Purge old entries from the dead-letter queue."""
    count = await dead_letter_queue.purge_old_entries(channel, max_age_hours)
    return {"channel": channel, "entries_purged": count}
