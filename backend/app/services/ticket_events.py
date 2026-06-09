import json
from datetime import UTC, datetime
from uuid import UUID

from app.core.redis import get_redis_client


def ticket_updates_channel(anonymous_user_id: UUID) -> str:
    return f"ticket:updates:{anonymous_user_id}"


class TicketEventPublisher:
    def __init__(self) -> None:
        self._redis = get_redis_client()

    async def publish_status_change(
        self,
        *,
        anonymous_user_id: UUID,
        ticket_id: UUID,
        status: str,
        priority: str,
    ) -> None:
        payload = {
            "event": "ticket.status_changed",
            "ticket_id": str(ticket_id),
            "status": status,
            "priority": priority,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        await self._redis.publish(
            ticket_updates_channel(anonymous_user_id),
            json.dumps(payload),
        )
