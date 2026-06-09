from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ChatWsEventType = Literal[
    "connected",
    "typing_start",
    "typing_stop",
    "still_working",
    "message",
    "ping",
    "pong",
    "error",
]


class ChatWsEvent(BaseModel):
    event: ChatWsEventType
    conversation_id: UUID | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)
