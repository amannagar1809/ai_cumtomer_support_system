"""Telegram channel connector implementation."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from app.services.channel_connector import ChannelConnector, NormalizedMessage
from app.services.telegram_parser import TelegramMessageParser

logger = logging.getLogger(__name__)


class TelegramConnector(ChannelConnector):
    """Telegram channel connector."""

    def __init__(self):
        super().__init__("telegram")
        self.parser = TelegramMessageParser()

    async def normalize_message(self, raw_message: dict[str, Any]) -> NormalizedMessage:
        """Normalize Telegram message to standard format."""
        from app.schemas.telegram import TelegramMessage

        telegram_message = TelegramMessage(**raw_message)
        parsed = self.parser.parse_message(telegram_message)

        # Extract channel-specific metadata
        metadata = {
            "telegram_user_id": parsed.telegram_user_id,
            "telegram_chat_id": parsed.telegram_chat_id,
            "message_id": parsed.message_id,
            "message_type": parsed.message_type,
            "username": parsed.username,
            "first_name": parsed.first_name,
            "last_name": parsed.last_name,
            "language_code": parsed.language_code,
            "is_command": parsed.is_command,
            "command": parsed.command,
            "reply_to_message_id": parsed.reply_to_message_id,
        }

        return NormalizedMessage(
            conversation_id=None,  # Will be set by router
            user_id=None,  # Will be set by router
            channel="telegram",
            channel_message_id=str(parsed.message_id),
            sender_type="customer",
            content=parsed.content,
            attachments=[
                {
                    "file_id": att.file_id,
                    "file_unique_id": att.file_unique_id,
                    "file_size": att.file_size,
                    "mime_type": att.mime_type,
                    "type": att.type,
                }
                for att in parsed.attachments
            ],
            timestamp=parsed.timestamp,
            language=parsed.language_code,
            metadata=metadata,
        )

    async def get_user_identifier(self, raw_message: dict[str, Any]) -> str:
        """Extract Telegram user ID from message."""
        from app.schemas.telegram import TelegramMessage

        telegram_message = TelegramMessage(**raw_message)
        parsed = self.parser.parse_message(telegram_message)
        return str(parsed.telegram_user_id)

    async def send_response(
        self, conversation_id: UUID, message: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        """Send response via Telegram."""
        try:
            from app.services.telegram_client import TelegramBotClient

            client = TelegramBotClient()

            # Get chat ID from metadata
            chat_id = metadata.get("telegram_chat_id") if metadata else None
            if not chat_id:
                logger.error("Chat ID not found in metadata for Telegram response")
                return False

            # Send text message
            await client.send_message(chat_id=chat_id, text=message)
            logger.info(f"Sent Telegram response to chat {chat_id}")
            return True

        except Exception as e:
            logger.exception(f"Failed to send Telegram response: {e}")
            return False
