"""Email channel connector implementation."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from app.services.channel_connector import ChannelConnector, NormalizedMessage
from app.services.email_parser import EmailParser

logger = logging.getLogger(__name__)


class EmailConnector(ChannelConnector):
    """Email channel connector."""

    def __init__(self):
        super().__init__("email")
        self.parser = EmailParser()

    async def normalize_message(self, raw_message: dict[str, Any]) -> NormalizedMessage:
        """Normalize email message to standard format."""
        from app.schemas.email import EmailWebhookPayload

        webhook_payload = EmailWebhookPayload(**raw_message)
        parsed = self.parser.parse_email(webhook_payload)

        # Extract channel-specific metadata
        metadata = {
            "from_email": parsed.from_email,
            "from_name": parsed.from_name,
            "subject": parsed.subject,
            "to_email": parsed.to_email,
            "cc_emails": parsed.cc_emails,
            "message_id": parsed.message_id,
            "in_reply_to": parsed.in_reply_to,
            "references": parsed.references,
            "thread_id": parsed.thread_id,
            "has_attachments": parsed.has_attachments,
            "attachment_count": parsed.attachment_count,
            "signature_detected": parsed.signature_detected,
            "quoted_reply_detected": parsed.quoted_reply_detected,
            "provider": parsed.provider,
        }

        return NormalizedMessage(
            conversation_id=None,  # Will be set by router
            user_id=None,  # Will be set by router
            channel="email",
            channel_message_id=parsed.message_id,
            sender_type="customer",
            content=parsed.body,
            attachments=parsed.attachments or [],
            timestamp=parsed.timestamp,
            language=parsed.language,
            metadata=metadata,
        )

    async def get_user_identifier(self, raw_message: dict[str, Any]) -> str:
        """Extract email address from email message."""
        from app.schemas.email import EmailWebhookPayload

        webhook_payload = EmailWebhookPayload(**raw_message)
        parsed = self.parser.parse_email(webhook_payload)
        return parsed.from_email

    async def send_response(
        self, conversation_id: UUID, message: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        """Send response via email."""
        try:
            from app.services.email_client import EmailClient

            client = EmailClient()

            # Get email address from metadata
            to_email = metadata.get("to_email") if metadata else None
            if not to_email:
                logger.error("Email address not found in metadata for email response")
                return False

            # Get thread info from metadata
            in_reply_to = metadata.get("in_reply_to") if metadata else None
            references = metadata.get("references") if metadata else None

            # Send email
            await client.send_email(
                to_email=to_email,
                subject=metadata.get("subject", "Re: Your Support Request") if metadata else "Re: Your Support Request",
                text=message,
                in_reply_to=in_reply_to,
                references=references,
            )
            logger.info(f"Sent email response to {to_email}")
            return True

        except Exception as e:
            logger.exception(f"Failed to send email response: {e}")
            return False
