from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.conversation import ConversationChannel
from app.schemas.chat_memory import ChatMemoryMessage
from app.schemas.upload import MessageAttachment


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


class ReturningUserResponse(BaseModel):
    is_returning_user: bool
    conversation_id: UUID | None = None
    last_active_at: datetime | None = None
    message_count: int = 0
    can_continue: bool = False


class ContinueConversationRequest(BaseModel):
    anonymous_user_id: UUID


class ConversationMessageResponse(BaseModel):
    id: UUID | None = None
    role: str
    content: str
    timestamp: datetime
    attachments: list[MessageAttachment] = Field(default_factory=list)


class ContinueConversationResponse(BaseModel):
    session_id: UUID
    conversation_id: UUID
    anonymous_user_id: UUID
    expires_at: datetime
    last_active_at: datetime
    messages: list[ConversationMessageResponse]
    context_loaded: bool = True


class ConversationMessagesResponse(BaseModel):
    conversation_id: UUID
    messages: list[ConversationMessageResponse]


class SendMessageRequest(BaseModel):
    anonymous_user_id: UUID
    content: str
    session_id: UUID | None = None
    attachments: list[MessageAttachment] = Field(default_factory=list)


class SendMessageResponse(BaseModel):
    message: ConversationMessageResponse


class RedactMessageRequest(BaseModel):
    anonymous_user_id: UUID
    reason: str = Field(min_length=1, max_length=255)


class RedactMessageResponse(BaseModel):
    message_id: UUID
    conversation_id: UUID
    redacted: bool = True
    redacted_at: datetime
