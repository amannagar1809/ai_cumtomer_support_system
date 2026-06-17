"""WhatsApp message parser service for converting WhatsApp messages to internal format."""

import logging
from datetime import datetime
from typing import Any

from app.schemas.whatsapp import (
    WhatsAppMessage,
    WhatsAppMessageAttachment,
    WhatsAppParsedMessage,
)

logger = logging.getLogger(__name__)


class WhatsAppMessageParser:
    """Parse incoming WhatsApp messages and convert to internal format."""

    def __init__(self):
        self.opt_out_keywords = {"stop", "unsubscribe", "cancel", "quit", "optout"}
        self.opt_in_keywords = {"start", "subscribe", "yes", "optin"}

    def parse_message(
        self, whatsapp_message: WhatsAppMessage, phone_number: str
    ) -> WhatsAppParsedMessage:
        """
        Parse a WhatsApp message into internal format.

        Args:
            whatsapp_message: Raw WhatsApp message from webhook
            phone_number: Sender's phone number

        Returns:
            Parsed message ready for internal processing
        """
        message_type = whatsapp_message.type
        content = None
        attachments = []
        is_opt_out = False
        is_opt_in = False
        context_message_id = None

        # Extract context if present (for quoted/replied messages)
        if whatsapp_message.context:
            context_message_id = whatsapp_message.context.get("id")

        # Parse based on message type
        if message_type == "text":
            content = self._parse_text_message(whatsapp_message)
            is_opt_out, is_opt_in = self._check_opt_keywords(content or "")

        elif message_type == "image":
            content, attachments = self._parse_image_message(whatsapp_message)

        elif message_type == "document":
            content, attachments = self._parse_document_message(whatsapp_message)

        elif message_type == "audio":
            content, attachments = self._parse_audio_message(whatsapp_message)

        elif message_type == "voice":
            content, attachments = self._parse_voice_message(whatsapp_message)

        elif message_type == "video":
            content, attachments = self._parse_video_message(whatsapp_message)

        elif message_type == "location":
            content = self._parse_location_message(whatsapp_message)

        elif message_type == "interactive":
            content, attachments = self._parse_interactive_message(whatsapp_message)

        elif message_type == "system":
            # System messages (e.g., opt-in/opt-out confirmations)
            content = self._parse_system_message(whatsapp_message)

        else:
            logger.warning(f"Unknown WhatsApp message type: {message_type}")
            content = f"[Unsupported message type: {message_type}]"

        # Parse timestamp
        timestamp = self._parse_timestamp(whatsapp_message.timestamp)

        return WhatsAppParsedMessage(
            phone_number=phone_number,
            message_id=whatsapp_message.id,
            message_type=message_type,
            content=content,
            attachments=attachments,
            timestamp=timestamp,
            is_opt_out=is_opt_out,
            is_opt_in=is_opt_in,
            context_message_id=context_message_id,
        )

    def _parse_text_message(self, message: WhatsAppMessage) -> str:
        """Parse text message content."""
        if message.text and "body" in message.text:
            return message.text["body"]
        return ""

    def _parse_image_message(
        self, message: WhatsAppMessage
    ) -> tuple[str | None, list[WhatsAppMessageAttachment]]:
        """Parse image message."""
        if not message.image:
            return None, []

        attachment = WhatsAppMessageAttachment(
            type="image",
            media_id=message.image.get("id", ""),
            mime_type=message.image.get("mime_type"),
            sha256=message.image.get("sha256"),
            file_size=message.image.get("file_size"),
            caption=message.image.get("caption"),
        )

        content = message.image.get("caption") or "[Image]"
        return content, [attachment]

    def _parse_document_message(
        self, message: WhatsAppMessage
    ) -> tuple[str | None, list[WhatsAppMessageAttachment]]:
        """Parse document message."""
        if not message.document:
            return None, []

        attachment = WhatsAppMessageAttachment(
            type="document",
            media_id=message.document.get("id", ""),
            mime_type=message.document.get("mime_type"),
            sha256=message.document.get("sha256"),
            file_size=message.document.get("file_size"),
            filename=message.document.get("filename"),
            caption=message.document.get("caption"),
        )

        content = message.document.get("caption") or message.document.get(
            "filename", "[Document]"
        )
        return content, [attachment]

    def _parse_audio_message(
        self, message: WhatsAppMessage
    ) -> tuple[str | None, list[WhatsAppMessageAttachment]]:
        """Parse audio message."""
        if not message.audio:
            return None, []

        attachment = WhatsAppMessageAttachment(
            type="audio",
            media_id=message.audio.get("id", ""),
            mime_type=message.audio.get("mime_type"),
            sha256=message.audio.get("sha256"),
            file_size=message.audio.get("file_size"),
        )

        return "[Audio]", [attachment]

    def _parse_voice_message(
        self, message: WhatsAppMessage
    ) -> tuple[str | None, list[WhatsAppMessageAttachment]]:
        """Parse voice message."""
        if not message.voice:
            return None, []

        attachment = WhatsAppMessageAttachment(
            type="voice",
            media_id=message.voice.get("id", ""),
            mime_type=message.voice.get("mime_type"),
            sha256=message.voice.get("sha256"),
            file_size=message.voice.get("file_size"),
        )

        return "[Voice message]", [attachment]

    def _parse_video_message(
        self, message: WhatsAppMessage
    ) -> tuple[str | None, list[WhatsAppMessageAttachment]]:
        """Parse video message."""
        if not message.video:
            return None, []

        attachment = WhatsAppMessageAttachment(
            type="video",
            media_id=message.video.get("id", ""),
            mime_type=message.video.get("mime_type"),
            sha256=message.video.get("sha256"),
            file_size=message.video.get("file_size"),
            caption=message.video.get("caption"),
        )

        content = message.video.get("caption") or "[Video]"
        return content, [attachment]

    def _parse_location_message(self, message: WhatsAppMessage) -> str:
        """Parse location message."""
        if message.location:
            lat = message.location.get("latitude", "")
            lng = message.location.get("longitude", "")
            name = message.location.get("name", "")
            address = message.location.get("address", "")
            return f"Location: {name} ({address}) - {lat}, {lng}"
        return "[Location]"

    def _parse_interactive_message(
        self, message: WhatsAppMessage
    ) -> tuple[str | None, list[WhatsAppMessageAttachment]]:
        """Parse interactive message (button, list, etc.)."""
        if not message.interactive:
            return None, []

        interactive_type = message.interactive.get("type", "")
        content = f"[Interactive: {interactive_type}]"

        # Extract button/list response
        if interactive_type == "button_reply":
            button_reply = message.interactive.get("button_reply", {})
            content = button_reply.get("title", "[Button selection]")
        elif interactive_type == "list_reply":
            list_reply = message.interactive.get("list_reply", {})
            content = list_reply.get("title", "[List selection]")

        return content, []

    def _parse_system_message(self, message: WhatsAppMessage) -> str:
        """Parse system message."""
        if message.system:
            system_type = message.system.get("type", "")
            body = message.system.get("body", "")
            return f"[System: {system_type}] {body}"
        return "[System message]"

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse WhatsApp timestamp string to datetime."""
        try:
            # WhatsApp timestamp is in seconds since epoch
            timestamp = datetime.fromtimestamp(int(timestamp_str))
            return timestamp
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to parse timestamp {timestamp_str}: {e}")
            return datetime.utcnow()

    def _check_opt_keywords(self, content: str) -> tuple[bool, bool]:
        """Check if message contains opt-in or opt-out keywords."""
        content_lower = content.lower().strip()
        is_opt_out = content_lower in self.opt_out_keywords
        is_opt_in = content_lower in self.opt_in_keywords
        return is_opt_out, is_opt_in
