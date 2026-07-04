"""Telegram bot schemas for webhook and message formats."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TelegramUser(BaseModel):
    """Telegram user information."""

    id: int
    is_bot: bool
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None


class TelegramChat(BaseModel):
    """Telegram chat information."""

    id: int
    type: str  # private, group, supergroup, channel
    title: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class TelegramMessage(BaseModel):
    """Telegram message structure."""

    message_id: int
    from_: TelegramUser | None = Field(None, alias="from")
    date: int  # Unix timestamp
    chat: TelegramChat
    text: str | None = None
    photo: list[dict[str, Any]] | None = None
    document: dict[str, Any] | None = None
    voice: dict[str, Any] | None = None
    audio: dict[str, Any] | None = None
    video: dict[str, Any] | None = None
    caption: str | None = None
    reply_to_message: dict[str, Any] | None = None
    entities: list[dict[str, Any]] = Field(default_factory=list)


class TelegramUpdate(BaseModel):
    """Telegram update from webhook."""

    update_id: int
    message: TelegramMessage | None = None
    callback_query: dict[str, Any] | None = None
    inline_query: dict[str, Any] | None = None


class TelegramWebhookPayload(BaseModel):
    """Telegram webhook payload (array of updates)."""

    updates: list[TelegramUpdate]


class TelegramAttachment(BaseModel):
    """Telegram attachment."""

    file_id: str
    file_unique_id: str
    file_size: int | None = None
    file_path: str | None = None
    mime_type: str | None = None
    type: str  # photo, document, voice, audio, video


class ParsedTelegramMessage(BaseModel):
    """Parsed Telegram message ready for internal processing."""

    telegram_user_id: int
    telegram_chat_id: int
    message_id: int
    message_type: str
    content: str | None = None
    attachments: list[TelegramAttachment] = Field(default_factory=list)
    timestamp: datetime
    username: str | None = None
    first_name: str
    last_name: str | None = None
    language_code: str | None = None
    is_command: bool = False
    command: str | None = None
    reply_to_message_id: int | None = None


class TelegramInlineKeyboardButton(BaseModel):
    """Inline keyboard button."""

    text: str
    callback_data: str | None = None
    url: str | None = None
    callback_game: dict[str, Any] | None = None
    switch_inline_query: str | None = None
    switch_inline_query_current_chat: str | None = None


class TelegramInlineKeyboardMarkup(BaseModel):
    """Inline keyboard markup."""

    inline_keyboard: list[list[TelegramInlineKeyboardButton]]


class TelegramReplyKeyboardMarkup(BaseModel):
    """Reply keyboard markup."""

    keyboard: list[list[dict[str, Any]]]
    resize_keyboard: bool = False
    one_time_keyboard: bool = False
    selective: bool = False


class TelegramSendMessageRequest(BaseModel):
    """Request to send message via Telegram bot."""

    chat_id: int | str
    text: str
    parse_mode: str | None = None  # Markdown, HTML
    disable_web_page_preview: bool = False
    disable_notification: bool = False
    reply_to_message_id: int | None = None
    reply_markup: dict[str, Any] | None = None


class TelegramSendPhotoRequest(BaseModel):
    """Request to send photo via Telegram bot."""

    chat_id: int | str
    photo: str  # file_id or URL
    caption: str | None = None
    parse_mode: str | None = None
    disable_notification: bool = False
    reply_to_message_id: int | None = None
    reply_markup: dict[str, Any] | None = None


class TelegramSendDocumentRequest(BaseModel):
    """Request to send document via Telegram bot."""

    chat_id: int | str
    document: str  # file_id or URL
    caption: str | None = None
    parse_mode: str | None = None
    disable_notification: bool = False
    reply_to_message_id: int | None = None
    reply_markup: dict[str, Any] | None = None


class TelegramSendMessageResponse(BaseModel):
    """Response from Telegram bot API."""

    ok: bool
    result: dict[str, Any] | None = None
    description: str | None = None
    error_code: int | None = None


class TelegramBotCommand(BaseModel):
    """Bot command."""

    command: str
    description: str


class TelegramBotInfo(BaseModel):
    """Bot information."""

    id: int
    is_bot: bool
    first_name: str
    username: str
    can_join_groups: bool
    can_read_all_group_messages: bool
    supports_inline_queries: bool
