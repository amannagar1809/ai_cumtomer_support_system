"""Mobile chat schemas for REST API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MobileMessage(BaseModel):
    """Mobile chat message."""

    id: UUID
    conversation_id: UUID
    sender_type: str  # "customer" or "agent"
    message: str
    timestamp: datetime
    language: str | None = None
    sentiment: str | None = None
    is_read: bool = False
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class MobileSendMessageRequest(BaseModel):
    """Request to send a message via mobile chat."""

    conversation_id: UUID | None = None
    message: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    device_id: str | None = None
    app_version: str | None = None


class MobileSendMessageResponse(BaseModel):
    """Response from sending a mobile message."""

    message_id: UUID
    conversation_id: UUID
    timestamp: datetime
    status: str


class MobileGetMessagesRequest(BaseModel):
    """Request to get messages for mobile chat."""

    conversation_id: UUID
    since: datetime | None = None
    limit: int = 50
    offset: int = 0


class MobileGetMessagesResponse(BaseModel):
    """Response with messages for mobile chat."""

    messages: list[MobileMessage]
    conversation_id: UUID
    has_more: bool
    last_timestamp: datetime | None = None


class MobileLongPollRequest(BaseModel):
    """Request for long-polling messages."""

    conversation_id: UUID
    last_message_id: UUID | None = None
    timeout: int = 30


class MobileLongPollResponse(BaseModel):
    """Response from long-polling."""

    messages: list[MobileMessage]
    conversation_id: UUID
    timeout_reached: bool


class MobileConversation(BaseModel):
    """Mobile conversation summary."""

    id: UUID
    user_id: UUID
    channel: str
    status: str
    started_at: datetime
    last_message_at: datetime | None = None
    message_count: int = 0
    unread_count: int = 0


class MobileConversationListResponse(BaseModel):
    """Response with list of conversations."""

    conversations: list[MobileConversation]
    total: int
    has_more: bool


class MobileOfflineMessage(BaseModel):
    """Offline message queued on device."""

    id: str
    conversation_id: UUID | None = None
    message: str
    timestamp: datetime
    device_id: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class MobileSyncRequest(BaseModel):
    """Request to sync offline messages."""

    device_id: str
    offline_messages: list[MobileOfflineMessage]
    last_sync_timestamp: datetime | None = None


class MobileSyncResponse(BaseModel):
    """Response from sync operation."""

    synced_message_ids: list[str]
    failed_message_ids: list[str]
    server_messages: list[MobileMessage]
    sync_timestamp: datetime


class MobilePushToken(BaseModel):
    """Mobile push notification token."""

    user_id: UUID
    device_id: str
    platform: str  # "ios" or "android"
    token: str
    app_version: str | None = None


class MobilePushNotification(BaseModel):
    """Push notification payload."""

    title: str
    body: str
    conversation_id: UUID | None = None
    message_id: UUID | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class MobileDeviceRegistration(BaseModel):
    """Mobile device registration."""

    device_id: str
    platform: str
    app_version: str
    push_token: str | None = None
    user_id: UUID | None = None


class MobileConnectionStatus(BaseModel):
    """Mobile connection status."""

    device_id: str
    online: bool
    last_seen: datetime
    network_type: str | None = None  # "wifi", "cellular", "none"
