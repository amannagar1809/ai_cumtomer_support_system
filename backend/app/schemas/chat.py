from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.conversation import ConversationChannel


class ChatSessionMetadata(BaseModel):
    locale: str = "en-US"
    page_url: str | None = None


class CreateChatSessionRequest(BaseModel):
    """Anonymous chat session init — no login required."""

    anonymous_user_id: UUID | None = None
    session_id: UUID | None = None
    conversation_id: UUID | None = None
    channel: ConversationChannel = ConversationChannel.web
    metadata: ChatSessionMetadata = Field(default_factory=ChatSessionMetadata)


class ChatGreetingMessage(BaseModel):
    role: str = "ai"
    content: str
    timestamp: datetime


class ChatSessionResponse(BaseModel):
    session_id: UUID
    conversation_id: UUID
    anonymous_user_id: UUID
    expires_at: datetime
    greeting: ChatGreetingMessage
    resumed: bool = False


class ChatSessionStatusResponse(BaseModel):
    session_id: UUID
    conversation_id: UUID
    anonymous_user_id: UUID
    expires_at: datetime
    greeting: ChatGreetingMessage
    metadata: dict[str, Any] = Field(default_factory=dict)
