from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QueueName(str, Enum):
    escalation = "escalation_queue"
    ticket_creation = "ticket_creation_queue"
    analytics = "analytics_queue"
    dead_letter = "dead_letter_queue"


def consumer_group_name(queue: QueueName) -> str:
    """Consumer group per stream, e.g. escalation_queue_workers."""
    return f"{queue.value}_workers"


class QueueMessage(BaseModel):
    """Message read from a Redis Stream."""

    stream: QueueName
    message_id: str
    event_type: str
    payload: dict[str, Any]
    correlation_id: str | None = None
    created_at: datetime | None = None
    attempt: int = 0
    not_before: float = 0
    last_error: str | None = None


class DeadLetterMessage(QueueMessage):
    """Failed message moved to dead_letter_queue after max retries."""

    source_stream: QueueName
    original_message_id: str
    final_attempt: int
    failed_at: datetime


class EscalationEvent(BaseModel):
    conversation_id: str
    user_id: str
    reason: str
    priority: str = "normal"
    metadata: dict[str, Any] = Field(default_factory=dict)


class TicketCreationEvent(BaseModel):
    conversation_id: str
    user_id: str
    category: str
    priority: str = "normal"
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalyticsEvent(BaseModel):
    event_type: str
    conversation_id: str | None = None
    user_id: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
