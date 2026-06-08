import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from redis.exceptions import ResponseError

from app.core.config import settings
from app.core.redis import get_queue_redis_client
from app.schemas.queue import (
    AnalyticsEvent,
    DeadLetterMessage,
    EscalationEvent,
    QueueMessage,
    QueueName,
    TicketCreationEvent,
    consumer_group_name,
)

ProcessHandler = Callable[[QueueMessage], Awaitable[None]]


class MessageQueueService:
    """Redis Streams message queues with consumer groups, ACK, retry, and DLQ."""

    def __init__(self) -> None:
        self._redis = get_queue_redis_client()

    @staticmethod
    def backoff_seconds(attempt: int) -> int:
        """Exponential backoff: base * 2^(attempt-1) → 1s, 2s, 4s by default."""
        return settings.queue_retry_base_seconds * (2 ** (attempt - 1))

    async def ensure_streams(self) -> None:
        """Create streams and consumer groups (idempotent)."""
        for queue in QueueName:
            group = consumer_group_name(queue)
            try:
                await self._redis.xgroup_create(
                    queue.value,
                    group,
                    id="0",
                    mkstream=True,
                )
            except ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise

    async def publish(
        self,
        queue: QueueName,
        *,
        event_type: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        attempt: int = 0,
        not_before: float = 0,
    ) -> str:
        fields = {
            "event_type": event_type,
            "payload": json.dumps(payload),
            "correlation_id": correlation_id or "",
            "created_at": datetime.now(UTC).isoformat(),
            "attempt": str(attempt),
            "not_before": str(not_before),
        }
        return await self._redis.xadd(queue.value, fields)

    async def publish_escalation(
        self,
        event: EscalationEvent,
        *,
        correlation_id: str | None = None,
    ) -> str:
        return await self.publish(
            QueueName.escalation,
            event_type="escalation.requested",
            payload=event.model_dump(),
            correlation_id=correlation_id,
        )

    async def publish_ticket_creation(
        self,
        event: TicketCreationEvent,
        *,
        correlation_id: str | None = None,
    ) -> str:
        return await self.publish(
            QueueName.ticket_creation,
            event_type="ticket.create",
            payload=event.model_dump(),
            correlation_id=correlation_id,
        )

    async def publish_analytics(
        self,
        event: AnalyticsEvent,
        *,
        correlation_id: str | None = None,
    ) -> str:
        return await self.publish(
            QueueName.analytics,
            event_type=event.event_type,
            payload=event.model_dump(),
            correlation_id=correlation_id,
        )

    async def read_group(
        self,
        queue: QueueName,
        *,
        consumer_name: str,
        count: int = 10,
        block_ms: int | None = None,
    ) -> list[QueueMessage]:
        """Read new messages for a consumer group member."""
        group = consumer_group_name(queue)
        block = block_ms if block_ms is not None else settings.queue_consumer_block_ms
        results = await self._redis.xreadgroup(
            groupname=group,
            consumername=consumer_name,
            streams={queue.value: ">"},
            count=count,
            block=block,
        )
        messages: list[QueueMessage] = []
        for _stream, entries in results or []:
            for message_id, fields in entries:
                messages.append(self._parse_message(queue, message_id, fields))
        return messages

    async def ack(self, queue: QueueName, message_id: str) -> int:
        """Acknowledge successful processing."""
        group = consumer_group_name(queue)
        return await self._redis.xack(queue.value, group, message_id)

    async def record_failure(
        self,
        queue: QueueName,
        message: QueueMessage,
        error: str,
    ) -> str | None:
        """
        Handle processing failure.
        Re-enqueue with exponential backoff or move to dead_letter_queue.
        Returns new message id on retry, None when sent to DLQ.
        """
        next_attempt = message.attempt + 1
        if next_attempt >= settings.queue_max_retry_attempts:
            await self.ack(queue, message.message_id)
            await self._send_to_dlq(queue, message, next_attempt, error)
            return None

        await self.ack(queue, message.message_id)
        delay = self.backoff_seconds(next_attempt)
        fields = {
            "event_type": message.event_type,
            "payload": json.dumps(message.payload),
            "correlation_id": message.correlation_id or "",
            "created_at": (message.created_at or datetime.now(UTC)).isoformat(),
            "attempt": str(next_attempt),
            "not_before": str(time.time() + delay),
            "last_error": error,
        }
        return await self._redis.xadd(queue.value, fields)

    async def _send_to_dlq(
        self,
        source_queue: QueueName,
        message: QueueMessage,
        final_attempt: int,
        error: str,
    ) -> str:
        fields = {
            "event_type": message.event_type,
            "payload": json.dumps(message.payload),
            "correlation_id": message.correlation_id or "",
            "created_at": (message.created_at or datetime.now(UTC)).isoformat(),
            "attempt": str(final_attempt),
            "not_before": "0",
            "source_stream": source_queue.value,
            "original_message_id": message.message_id,
            "final_attempt": str(final_attempt),
            "failed_at": datetime.now(UTC).isoformat(),
            "last_error": error,
        }
        return await self._redis.xadd(QueueName.dead_letter.value, fields)

    async def read_dead_letter(
        self,
        consumer_name: str,
        *,
        count: int = 10,
    ) -> list[DeadLetterMessage]:
        group = consumer_group_name(QueueName.dead_letter)
        results = await self._redis.xreadgroup(
            groupname=group,
            consumername=consumer_name,
            streams={QueueName.dead_letter.value: ">"},
            count=count,
            block=0,
        )
        messages: list[DeadLetterMessage] = []
        for _stream, entries in results or []:
            for message_id, fields in entries:
                messages.append(self._parse_dead_letter(message_id, fields))
        return messages

    async def get_pending_count(self, queue: QueueName) -> int:
        """Unacknowledged messages in the consumer group."""
        group = consumer_group_name(queue)
        pending = await self._redis.xpending(queue.value, group)
        return int(pending.get("pending", 0) if isinstance(pending, dict) else pending[0])

    async def process_batch(
        self,
        queue: QueueName,
        *,
        consumer_name: str,
        handler: ProcessHandler,
        count: int = 10,
    ) -> int:
        """Read, process, ACK on success; retry or DLQ on failure."""
        processed = 0
        messages = await self.read_group(queue, consumer_name=consumer_name, count=count)
        for message in messages:
            if message.not_before > time.time():
                continue
            try:
                await handler(message)
            except Exception as exc:
                await self.record_failure(queue, message, str(exc))
            else:
                await self.ack(queue, message.message_id)
                processed += 1
        return processed

    def _parse_message(
        self,
        queue: QueueName,
        message_id: str,
        fields: dict[str, str],
    ) -> QueueMessage:
        created_raw = fields.get("created_at")
        created_at = (
            datetime.fromisoformat(created_raw) if created_raw else None
        )
        correlation = fields.get("correlation_id") or None
        return QueueMessage(
            stream=queue,
            message_id=message_id,
            event_type=fields.get("event_type", ""),
            payload=json.loads(fields.get("payload", "{}")),
            correlation_id=correlation,
            created_at=created_at,
            attempt=int(fields.get("attempt", "0")),
            not_before=float(fields.get("not_before", "0")),
            last_error=fields.get("last_error"),
        )

    def _parse_dead_letter(
        self,
        message_id: str,
        fields: dict[str, str],
    ) -> DeadLetterMessage:
        base = self._parse_message(QueueName.dead_letter, message_id, fields)
        failed_raw = fields.get("failed_at")
        return DeadLetterMessage(
            **base.model_dump(),
            source_stream=QueueName(fields["source_stream"]),
            original_message_id=fields["original_message_id"],
            final_attempt=int(fields.get("final_attempt", "0")),
            failed_at=(
                datetime.fromisoformat(failed_raw)
                if failed_raw
                else datetime.now(UTC)
            ),
        )
