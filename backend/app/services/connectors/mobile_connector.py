"""Mobile channel connector implementation."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from app.services.channel_connector import ChannelConnector, NormalizedMessage

logger = logging.getLogger(__name__)


class MobileConnector(ChannelConnector):
    """Mobile channel connector."""

    def __init__(self):
        super().__init__("mobile")

    async def normalize_message(self, raw_message: dict[str, Any]) -> NormalizedMessage:
        """Normalize mobile message to standard format."""
        from app.schemas.mobile_chat import MobileSendMessageRequest

        mobile_request = MobileSendMessageRequest(**raw_message)

        # Extract channel-specific metadata
        metadata = {
            "device_id": mobile_request.device_id,
            "app_version": mobile_request.app_version,
            "attachment_count": len(mobile_request.attachments),
        }

        return NormalizedMessage(
            conversation_id=mobile_request.conversation_id,
            user_id=None,  # Will be set by router
            channel="mobile",
            channel_message_id="",  # Mobile messages don't have external IDs
            sender_type="customer",
            content=mobile_request.message,
            attachments=mobile_request.attachments,
            timestamp=datetime.utcnow(),
            language=None,
            metadata=metadata,
        )

    async def get_user_identifier(self, raw_message: dict[str, Any]) -> str:
        """Extract device ID from mobile message."""
        from app.schemas.mobile_chat import MobileSendMessageRequest

        mobile_request = MobileSendMessageRequest(**raw_message)
        return mobile_request.device_id or "unknown"

    async def send_response(
        self, conversation_id: UUID, message: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        """Send response via mobile (push notification)."""
        try:
            from app.services.mobile_push import MobilePushService
            from app.schemas.mobile_chat import MobilePushNotification

            push_service = MobilePushService()

            # Get user ID from conversation
            # In a real implementation, you would query the database for the user
            # For now, we'll just log
            logger.info(f"Would send push notification for conversation {conversation_id}")

            # Create push notification
            notification = MobilePushNotification(
                title="New Support Message",
                body=message[:100] + "..." if len(message) > 100 else message,
                conversation_id=conversation_id,
                data={"conversation_id": str(conversation_id)},
            )

            # Send push notification
            # await push_service.send_to_conversation(str(conversation_id), notification)
            return True

        except Exception as e:
            logger.exception(f"Failed to send mobile response: {e}")
            return False
