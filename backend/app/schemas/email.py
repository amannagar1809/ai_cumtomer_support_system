"""Email support schemas for webhook and message formats."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr


class EmailAddress(BaseModel):
    """Email address with optional name."""

    email: EmailStr
    name: str | None = None


class EmailAttachment(BaseModel):
    """Email attachment."""

    filename: str
    content_type: str
    size: int
    content_id: str | None = None
    url: str | None = None
    data: str | None = None  # Base64 encoded content


class EmailWebhookPayload(BaseModel):
    """Incoming email webhook payload (Postmark/SendGrid format)."""

    from_address: EmailAddress = Field(..., alias="From")
    to_address: list[EmailAddress] = Field(..., alias="To")
    subject: str = Field(..., alias="Subject")
    message_id: str = Field(..., alias="MessageID")
    reply_to: list[EmailAddress] | None = Field(None, alias="ReplyTo")
    cc: list[EmailAddress] | None = Field(None, alias="Cc")
    bcc: list[EmailAddress] | None = Field(None, alias="Bcc")
    text_body: str | None = Field(None, alias="TextBody")
    html_body: str | None = Field(None, alias="HtmlBody")
    attachments: list[EmailAttachment] = Field(default_factory=list, alias="Attachments")
    headers: dict[str, str] = Field(default_factory=dict, alias="Headers")
    received_at: datetime = Field(default_factory=datetime.utcnow)
    in_reply_to: str | None = Field(None, alias="InReplyTo")
    references: list[str] = Field(default_factory=list, alias="References")
    thread_id: str | None = None


class ParsedEmailMessage(BaseModel):
    """Parsed email message ready for internal processing."""

    message_id: str
    from_email: str
    from_name: str | None
    to_emails: list[str]
    subject: str
    text_body: str | None
    html_body: str | None
    attachments: list[EmailAttachment]
    received_at: datetime
    in_reply_to: str | None
    references: list[str]
    thread_id: str | None
    extracted_body: str  # Body with quoted replies and signatures removed
    is_reply: bool
    conversation_id: UUID | None


class EmailSignaturePattern(BaseModel):
    """Email signature pattern for detection."""

    pattern: str
    is_regex: bool = False


class EmailSignatureDetection(BaseModel):
    """Detected email signature information."""

    has_signature: bool
    signature_start: int | None
    signature_text: str | None
    confidence: float


class EmailReplyPattern(BaseModel):
    """Email reply pattern for quoted text detection."""

    pattern: str
    is_regex: bool = False


class EmailQuotedReply(BaseModel):
    """Detected quoted reply information."""

    has_quoted_text: bool
    quoted_text: str
    quoted_start: int
    clean_body: str


class EmailThreadInfo(BaseModel):
    """Email thread information."""

    thread_id: str
    message_count: int
    first_message_id: str
    last_message_id: str
    conversation_id: UUID | None


class SendEmailRequest(BaseModel):
    """Request to send an email."""

    to: EmailStr | list[EmailStr]
    subject: str
    text_body: str | None = None
    html_body: str | None = None
    from_address: EmailStr | None = None
    from_name: str | None = None
    reply_to: EmailStr | None = None
    cc: list[EmailStr] = Field(default_factory=list)
    bcc: list[EmailStr] = Field(default_factory=list)
    attachments: list[EmailAttachment] = Field(default_factory=list)
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    message_id: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class SendEmailResponse(BaseModel):
    """Response from email sending API."""

    message_id: str
    to: str | list[str]
    subject: str
    sent_at: datetime
    provider: str


class EmailRateLimitInfo(BaseModel):
    """Email rate limit information."""

    email: str
    sent_today: int
    limit: int
    remaining: int
    reset_at: datetime
