"""WhatsApp Business API schemas for webhook and message formats."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class WhatsAppWebhookVerifyRequest(BaseModel):
    """Meta webhook verification request."""

    mode: str = Field(..., alias="hub.mode")
    challenge: str = Field(..., alias="hub.challenge")
    verify_token: str = Field(..., alias="hub.verify_token")


class WhatsAppContact(BaseModel):
    """WhatsApp contact information."""

    profile: dict[str, Any] | None = None
    wa_id: str | None = None


class WhatsAppMessage(BaseModel):
    """Base WhatsApp message structure."""

    from_: str = Field(..., alias="from")
    id: str
    timestamp: str
    context: dict[str, Any] | None = None
    type: str

    text: dict[str, Any] | None = None
    image: dict[str, Any] | None = None
    document: dict[str, Any] | None = None
    audio: dict[str, Any] | None = None
    voice: dict[str, Any] | None = None
    video: dict[str, Any] | None = None
    location: dict[str, Any] | None = None
    interactive: dict[str, Any] | None = None
    system: dict[str, Any] | None = None


class WhatsAppChange(BaseModel):
    """Webhook change object."""

    field: str
    value: dict[str, Any]


class WhatsAppEntry(BaseModel):
    """Webhook entry object."""

    id: str
    changes: list[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    """Complete WhatsApp webhook payload."""

    object: str
    entry: list[WhatsAppEntry]


class WhatsAppOptStatus(str):
    """WhatsApp opt-in/opt-out status."""

    opted_in = "opted_in"
    opted_out = "opted_out"


class WhatsAppUserProfile(BaseModel):
    """WhatsApp user profile information."""

    wa_id: str
    name: str | None = None
    phone: str


class WhatsAppMessageAttachment(BaseModel):
    """WhatsApp message attachment."""

    type: str  # image, document, audio, voice, video
    media_id: str
    mime_type: str | None = None
    sha256: str | None = None
    file_size: int | None = None
    url: str | None = None


class WhatsAppParsedMessage(BaseModel):
    """Parsed WhatsApp message ready for internal processing."""

    phone_number: str
    message_id: str
    message_type: str
    content: str | None = None
    attachments: list[WhatsAppMessageAttachment] = Field(default_factory=list)
    timestamp: datetime
    is_opt_out: bool = False
    is_opt_in: bool = False
    context_message_id: str | None = None


class WhatsAppTemplateMessage(BaseModel):
    """WhatsApp template message for sending."""

    name: str
    language: dict[str, str]
    components: list[dict[str, Any]] = Field(default_factory=list)


class WhatsAppTextMessage(BaseModel):
    """WhatsApp text message for sending."""

    body: str
    preview_url: bool = False


class WhatsAppMediaMessage(BaseModel):
    """WhatsApp media message for sending."""

    media_type: str  # image, document, audio, video
    media_id: str | None = None
    url: str | None = None
    caption: str | None = None
    filename: str | None = None


class WhatsAppSendMessageRequest(BaseModel):
    """Request to send message via WhatsApp API."""

    to: str  # WhatsApp phone number
    message_type: str  # text, template, image, document, audio
    text: WhatsAppTextMessage | None = None
    template: WhatsAppTemplateMessage | None = None
    media: WhatsAppMediaMessage | None = None
    context: dict[str, Any] | None = None  # For quoted/replied messages


class WhatsAppSendMessageResponse(BaseModel):
    """Response from WhatsApp API send message."""

    messaging_product: str
    contacts: list[dict[str, Any]]
    messages: list[dict[str, Any]]


class WhatsAppOptInRequest(BaseModel):
    """Request to opt-in to WhatsApp messages."""

    phone_number: str
    template_name: str | None = None


class WhatsAppOptOutRequest(BaseModel):
    """Request to opt-out from WhatsApp messages."""

    phone_number: str
    reason: str | None = None


class WhatsAppOptStatusResponse(BaseModel):
    """Response for opt-in/opt-out status."""

    phone_number: str
    status: WhatsAppOptStatus
    opted_at: datetime | None = None
    opted_out_at: datetime | None = None
