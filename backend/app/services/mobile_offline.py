"""Mobile offline message queueing and sync service."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_session
from app.core.redis import get_redis_client
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.mobile_chat import (
    MobileMessage,
    MobileOfflineMessage,
    MobileSyncRequest,
    MobileSyncResponse,
)

logger = logging.getLogger(__name__)


class MobileOfflineService:
    """Service for handling offline message queueing and sync."""

    def __init__(self):
        self.redis_prefix = "mobile_offline"
        self.max_offline_messages = settings.mobile_max_offline_messages

    async def queue_offline_message(
        self,
        device_id: str,
        message: str,
        conversation_id: UUID | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Queue an offline message for a device.

        Args:
            device_id: Device ID
            message: Message content
            conversation_id: Conversation ID (optional)
            attachments: Message attachments

        Returns:
            Message ID
        """
        redis = await get_redis_client()

        try:
            message_id = str(uuid4())
            offline_message = MobileOfflineMessage(
                id=message_id,
                conversation_id=conversation_id,
                message=message,
                timestamp=datetime.utcnow(),
                device_id=device_id,
                attachments=attachments or [],
            )

            key = f"{self.redis_prefix}:{device_id}"
            await redis.lpush(key, offline_message.model_dump_json())
            await redis.ltrim(key, 0, self.max_offline_messages - 1)

            logger.info(f"Queued offline message {message_id} for device {device_id}")
            return message_id

        except Exception as e:
            logger.exception(f"Error queuing offline message: {e}")
            raise

    async def get_offline_messages(
        self, device_id: str, limit: int | None = None
    ) -> list[MobileOfflineMessage]:
        """
        Get offline messages for a device.

        Args:
            device_id: Device ID
            limit: Maximum number of messages to retrieve

        Returns:
            List of offline messages
        """
        redis = await get_redis_client()

        try:
            key = f"{self.redis_prefix}:{device_id}"
            messages_json = await redis.lrange(key, 0, limit or -1)

            messages = []
            for msg_json in messages_json:
                try:
                    msg = MobileOfflineMessage.model_validate_json(msg_json)
                    messages.append(msg)
                except Exception as e:
                    logger.warning(f"Failed to parse offline message: {e}")

            return messages

        except Exception as e:
            logger.exception(f"Error getting offline messages: {e}")
            return []

    async def clear_offline_messages(self, device_id: str) -> int:
        """
        Clear all offline messages for a device.

        Args:
            device_id: Device ID

        Returns:
            Number of messages cleared
        """
        redis = await get_redis_client()

        try:
            key = f"{self.redis_prefix}:{device_id}"
            count = await redis.llen(key)
            await redis.delete(key)
            logger.info(f"Cleared {count} offline messages for device {device_id}")
            return count

        except Exception as e:
            logger.exception(f"Error clearing offline messages: {e}")
            return 0

    async def sync_offline_messages(
        self,
        request: MobileSyncRequest,
        user_id: UUID,
    ) -> MobileSyncResponse:
        """
        Sync offline messages from device to server.

        Args:
            request: Sync request with offline messages
            user_id: User ID

        Returns:
            Sync response with results
        """
        if not settings.mobile_offline_queue_enabled:
            raise ValueError("Offline queueing is not enabled")

        async for session in get_async_session():
            try:
                synced_ids = []
                failed_ids = []
                server_messages = []

                # Process each offline message
                for offline_msg in request.offline_messages:
                    try:
                        # Get or create conversation
                        if offline_msg.conversation_id:
                            result = await session.execute(
                                select(Conversation).where(
                                    Conversation.id == offline_msg.conversation_id,
                                    Conversation.user_id == user_id,
                                )
                            )
                            conversation = result.scalar_one_or_none()
                        else:
                            conversation = None

                        if not conversation:
                            # Create new conversation
                            conversation = Conversation(
                                user_id=user_id,
                                channel="web",
                                status="active",
                            )
                            session.add(conversation)
                            await session.flush()
                            await session.refresh(conversation)

                        # Create message
                        message = Message(
                            conversation_id=conversation.id,
                            sender_type="customer",
                            message=offline_msg.message,
                            language="en",
                        )
                        session.add(message)
                        await session.flush()
                        await session.refresh(message)

                        synced_ids.append(offline_msg.id)

                        # Queue for AI processing
                        from app.services.message_queue import MessageQueueService

                        queue = MessageQueueService()
                        internal_message = {
                            "conversation_id": str(conversation.id),
                            "message_id": str(message.id),
                            "user_id": str(user_id),
                            "message": offline_msg.message,
                            "sender_type": "customer",
                            "channel": "mobile",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        await queue.add_to_queue("mobile_queue", internal_message)

                    except Exception as e:
                        logger.exception(f"Error syncing message {offline_msg.id}: {e}")
                        failed_ids.append(offline_msg.id)

                await session.commit()

                # Get new messages from server since last sync
                if request.last_sync_timestamp:
                    server_messages = await self._get_new_messages(
                        session, user_id, request.last_sync_timestamp
                    )

                # Clear offline messages from device queue
                await self.clear_offline_messages(request.device_id)

                return MobileSyncResponse(
                    synced_message_ids=synced_ids,
                    failed_message_ids=failed_ids,
                    server_messages=server_messages,
                    sync_timestamp=datetime.utcnow(),
                )

            except Exception as e:
                logger.exception(f"Error syncing offline messages: {e}")
                await session.rollback()
                raise

    async def _get_new_messages(
        self,
        session: AsyncSession,
        user_id: UUID,
        since: datetime,
    ) -> list[MobileMessage]:
        """Get new messages for user since a timestamp."""
        try:
            # Get user's conversations
            result = await session.execute(
                select(Conversation).where(Conversation.user_id == user_id)
            )
            conversations = result.scalars().all()

            conversation_ids = [conv.id for conv in conversations]

            # Get messages since timestamp
            result = await session.execute(
                select(Message)
                .where(
                    Message.conversation_id.in_(conversation_ids),
                    Message.timestamp >= since,
                )
                .order_by(Message.timestamp.asc())
                .limit(100)
            )
            messages = result.scalars().all()

            return [
                MobileMessage(
                    id=msg.id,
                    conversation_id=msg.conversation_id,
                    sender_type=msg.sender_type,
                    message=msg.message,
                    timestamp=msg.timestamp,
                    language=msg.language,
                    sentiment=msg.sentiment,
                    is_read=False,
                )
                for msg in messages
            ]

        except Exception as e:
            logger.exception(f"Error getting new messages: {e}")
            return []

    async def get_device_status(self, device_id: str) -> dict[str, Any]:
        """
        Get offline queue status for a device.

        Args:
            device_id: Device ID

        Returns:
            Device status information
        """
        redis = await get_redis_client()

        try:
            key = f"{self.redis_prefix}:{device_id}"
            count = await redis.llen(key)

            return {
                "device_id": device_id,
                "offline_message_count": count,
                "max_offline_messages": self.max_offline_messages,
                "queue_enabled": settings.mobile_offline_queue_enabled,
            }

        except Exception as e:
            logger.exception(f"Error getting device status: {e}")
            return {
                "device_id": device_id,
                "offline_message_count": 0,
                "error": str(e),
            }
