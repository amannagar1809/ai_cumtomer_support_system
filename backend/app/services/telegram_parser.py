"""Telegram message parser service for parsing incoming bot messages."""

import logging
from datetime import datetime
from typing import Any

from app.schemas.telegram import (
    ParsedTelegramMessage,
    TelegramAttachment,
    TelegramMessage,
)

logger = logging.getLogger(__name__)


class TelegramMessageParser:
    """Parse incoming Telegram messages and convert to internal format."""

    def __init__(self):
        self.bot_commands = ["/start", "/help", "/ticket", "/status", "/stop"]

    def parse_message(self, telegram_message: TelegramMessage) -> ParsedTelegramMessage:
        """
        Parse a Telegram message into internal format.

        Args:
            telegram_message: Raw Telegram message from webhook

        Returns:
            Parsed message ready for internal processing
        """
        # Extract user information
        user = telegram_message.from_
        chat = telegram_message.chat

        telegram_user_id = user.id if user else chat.id
        telegram_chat_id = chat.id
        message_id = telegram_message.message_id

        # Extract user details
        username = user.username if user else None
        first_name = user.first_name if user else chat.first_name
        last_name = user.last_name if user else chat.last_name
        language_code = user.language_code if user else None

        # Parse timestamp
        timestamp = datetime.fromtimestamp(telegram_message.date)

        # Determine message type and content
        message_type, content, attachments = self._parse_message_content(telegram_message)

        # Check if message is a command
        is_command, command = self._check_command(content or "")

        # Check if this is a reply to another message
        reply_to_message_id = None
        if telegram_message.reply_to_message:
            reply_to_message_id = telegram_message.reply_to_message.get("message_id")

        return ParsedTelegramMessage(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            message_id=message_id,
            message_type=message_type,
            content=content,
            attachments=attachments,
            timestamp=timestamp,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            is_command=is_command,
            command=command,
            reply_to_message_id=reply_to_message_id,
        )

    def _parse_message_content(
        self, message: TelegramMessage
    ) -> tuple[str, str | None, list[TelegramAttachment]]:
        """Parse message content based on type."""
        attachments = []
        content = None
        message_type = "text"

        # Check for text message
        if message.text:
            content = message.text
            message_type = "text"

        # Check for photo
        elif message.photo:
            message_type = "photo"
            # Get the largest photo
            largest_photo = message.photo[-1] if message.photo else None
            if largest_photo:
                attachments.append(
                    TelegramAttachment(
                        file_id=largest_photo.get("file_id", ""),
                        file_unique_id=largest_photo.get("file_unique_id", ""),
                        file_size=largest_photo.get("file_size"),
                        type="photo",
                    )
                )
            content = message.caption

        # Check for document
        elif message.document:
            message_type = "document"
            doc = message.document
            attachments.append(
                TelegramAttachment(
                    file_id=doc.get("file_id", ""),
                    file_unique_id=doc.get("file_unique_id", ""),
                    file_size=doc.get("file_size"),
                    mime_type=doc.get("mime_type"),
                    type="document",
                )
            )
            content = message.caption or doc.get("file_name", "[Document]")

        # Check for voice
        elif message.voice:
            message_type = "voice"
            voice = message.voice
            attachments.append(
                TelegramAttachment(
                    file_id=voice.get("file_id", ""),
                    file_unique_id=voice.get("file_unique_id", ""),
                    file_size=voice.get("file_size"),
                    mime_type=voice.get("mime_type"),
                    type="voice",
                )
            )
            content = "[Voice message]"

        # Check for audio
        elif message.audio:
            message_type = "audio"
            audio = message.audio
            attachments.append(
                TelegramAttachment(
                    file_id=audio.get("file_id", ""),
                    file_unique_id=audio.get("file_unique_id", ""),
                    file_size=audio.get("file_size"),
                    mime_type=audio.get("mime_type"),
                    type="audio",
                )
            )
            content = message.caption or audio.get("title", "[Audio]")

        # Check for video
        elif message.video:
            message_type = "video"
            video = message.video
            attachments.append(
                TelegramAttachment(
                    file_id=video.get("file_id", ""),
                    file_unique_id=video.get("file_unique_id", ""),
                    file_size=video.get("file_size"),
                    mime_type=video.get("mime_type"),
                    type="video",
                )
            )
            content = message.caption or "[Video]"

        else:
            message_type = "unknown"
            content = "[Unsupported message type]"

        return message_type, content, attachments

    def _check_command(self, content: str) -> tuple[bool, str | None]:
        """Check if message is a bot command."""
        if not content:
            return False, None

        content_stripped = content.strip()
        if content_stripped.startswith("/"):
            parts = content_stripped.split()
            command = parts[0].lower()
            return True, command

        return False, None

    def truncate_message(self, text: str, max_length: int = 4096) -> str:
        """
        Truncate message to fit Telegram limits.

        Args:
            text: Message text
            max_length: Maximum length (default 4096 for Telegram)

        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= max_length:
            return text

        return text[: max_length - 3] + "..."

    def validate_file_size(self, file_size: int, max_size_mb: int = 50) -> bool:
        """
        Validate file size against Telegram limits.

        Args:
            file_size: File size in bytes
            max_size_mb: Maximum size in MB

        Returns:
            True if file size is valid
        """
        max_bytes = max_size_mb * 1024 * 1024
        return file_size <= max_bytes
