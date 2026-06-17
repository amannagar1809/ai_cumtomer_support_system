"""WhatsApp channel connector implementation."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from app.services.channel_connector import ChannelConnector, NormalizedMessage
from app.services.whatsapp_parser import WhatsAppMessageParser

logger = logging.getLogger(__name__)


class WhatsAppConnector(ChannelConnector):
    """WhatsApp channel connector."""

    def __init__(self):
        super().__init__("whatsapp")
        self.parser = WhatsAppMessageParser()

    async def normalize_message(self, raw_message: dict[str, Any]) -> NormalizedMessage:
        """Normalize WhatsApp message to standard format."""
        from app.schemas.whatsapp import WhatsAppWebhookMessage

        webhook_message = WhatsAppWebhookMessage(**raw_message)
        parsed = self.parser.parse_message(webhook_message)

        # Extract channel-specific metadata
        metadata = {
            "phone_number": parsed.phone_number,
            "message_type": parsed.message_type,
            "is_opt_in": parsed.is_opt_in,
            "is_opt_out": parsed.is_opt_out,
            "media_url": parsed.media_url,
            "media_type": parsed.media_type,
            "template_name": parsed.template_name,
            "interactive_type": parsed.interactive_type,
            "interactive_data": parsed.interactive_data,
            "context_message_id": parsed.context_message_id,
        }

        return NormalizedMessage(
            conversation_id=None,  # Will be set by router
            user_id=None,  # Will be set by router
            channel="whatsapp",
            channel_message_id=parsed.message_id,
            sender_type="customer",
            content=parsed.message,
            attachments=parsed.attachments or [],
            timestamp=parsed.timestamp,
            language=parsed.language,
            metadata=metadata,
        )

    async def get_user_identifier(self, raw_message: dict[str, Any]) -> str:
        """Extract phone number from WhatsApp message."""
        from app.schemas.whatsapp import WhatsAppWebhookMessage

        webhook_message = WhatsAppWebhookMessage(**raw_message)
        parsed = self.parser.parse_message(webhook_message)
        return parsed.phone_number

    async def send_response(
        self, conversation_id: UUID, message: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        """Send response via WhatsApp."""
        try:
            from app.services.whatsapp_client import WhatsAppAPIClient

            client = WhatsAppAPIClient()

            # Get phone number from metadata or conversation
            phone_number = metadata.get("phone_number") if metadata else None
            if not phone_number:
                logger.error("Phone number not found in metadata for WhatsApp response")
                return False

            # Send text message
            await client.send_text_message(phone_number, message)
            logger.info(f"Sent WhatsApp response to {phone_number}")
            return True

        except Exception as e:
            logger.exception(f"Failed to send WhatsApp response: {e}")
            return False
