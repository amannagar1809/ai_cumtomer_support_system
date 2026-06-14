from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ChatWsMessageType = Literal["message", "typing", "read_receipt"]

ChatWsEventType = Literal[
    "connected",
    "typing_start",
    "typing_stop",
    "still_working",
    "message",
    "read_receipt",
    "ping",
    "pong",
    "error",
]


class ChatWsEvent(BaseModel):
    event: ChatWsEventType
    conversation_id: UUID | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)
    sequence: int | None = None


class ChatWsProtocolMessage(BaseModel):
    type: ChatWsMessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sequence: int | None = None
