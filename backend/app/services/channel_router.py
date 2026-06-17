"""Channel router for mapping incoming webhooks to conversation handlers."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.models.conversation import Conversation, ConversationChannel
from app.models.message import Message
from app.models.user import User
from app.services.channel_connector import ChannelConnector, NormalizedMessage
from app.services.connectors.email_connector import EmailConnector
from app.services.connectors.mobile_connector import MobileConnector
from app.services.connectors.telegram_connector import TelegramConnector
from app.services.connectors.whatsapp_connector import WhatsAppConnector
from app.services.dead_letter_queue import DeadLetterQueue

logger = logging.getLogger(__name__)


class ChannelRouter:
    """Router for channel-specific message handling."""

    def __init__(self):
        self.connectors: dict[str, ChannelConnector] = {
            "whatsapp": WhatsAppConnector(),
            "email": EmailConnector(),
            "telegram": TelegramConnector(),
            "mobile": MobileConnector(),
        }
        self.dead_letter_queue = DeadLetterQueue()

    def get_connector(self, channel: str) -> ChannelConnector:
        """
        Get the connector for a specific channel.

        Args:
            channel: Channel name

        Returns:
            Channel connector instance

        Raises:
            ValueError: If channel is not supported
        """
        connector = self.connectors.get(channel)
        if not connector:
            raise ValueError(f"Unsupported channel: {channel}")
        return connector

    async def route_message(
        self, channel: str, raw_message: dict[str, Any]
    ) -> NormalizedMessage:
        """
        Route a raw message through the appropriate channel connector.

        Args:
            channel: Channel name
            raw_message: Raw message from the channel

        Returns:
            Normalized message

        Raises:
            Exception: If routing fails
        """
        try:
            connector = self.get_connector(channel)
            normalized = await connector.process_message(raw_message)
            return normalized
        except Exception as e:
            logger.exception(f"Failed to route message from {channel}: {e}")
            # Send to dead-letter queue
            await self.dead_letter_queue.add_message(channel, raw_message, str(e))
            raise

    async def handle_message(self, channel: str, raw_message: dict[str, Any]) -> dict[str, Any]:
        """
        Handle a message from a channel end-to-end.

        Args:
            channel: Channel name
            raw_message: Raw message from the channel

        Returns:
            Result dictionary with message and conversation IDs
        """
        try:
            # Normalize the message
            normalized = await self.route_message(channel, raw_message)

            # Get or create user
            async for session in get_async_session():
                try:
                    user = await self._get_or_create_user(
                        session, channel, normalized, raw_message
                    )

                    # Get or create conversation
                    conversation = await self._get_or_create_conversation(
                        session, user, channel, normalized
                    )

                    # Create message in database
                    message = await self._create_message(
                        session, conversation, normalized
                    )

                    # Queue for AI processing
                    await self._queue_for_processing(conversation, message, user, normalized)

                    return {
                        "success": True,
                        "message_id": str(message.id),
                        "conversation_id": str(conversation.id),
                        "user_id": str(user.id),
                        "channel": channel,
                    }

                except Exception as e:
                    logger.exception(f"Error handling message: {e}")
                    await session.rollback()
                    raise

        except Exception as e:
            logger.exception(f"Failed to handle message from {channel}: {e}")
            return {
                "success": False,
                "error": str(e),
                "channel": channel,
            }

    async def _get_or_create_user(
        self,
        session: AsyncSession,
        channel: str,
        normalized: NormalizedMessage,
        raw_message: dict[str, Any],
    ) -> User:
        """Get or create user based on channel."""
        connector = self.get_connector(channel)
        user_identifier = await connector.get_user_identifier(raw_message)

        # Try to find existing user
        if channel == "whatsapp":
            result = await session.execute(
                select(User).where(User.phone == user_identifier)
            )
        elif channel == "email":
            result = await session.execute(
                select(User).where(User.email == user_identifier)
            )
        elif channel == "telegram":
            result = await session.execute(
                select(User).where(User.email == f"telegram_{user_identifier}")
            )
        else:  # mobile
            # For mobile, user should already be authenticated
            result = await session.execute(select(User).limit(1))

        user = result.scalar_one_or_none()

        if not user:
            # Create new user
            if channel == "whatsapp":
                user = User(
                    name=f"WhatsApp User {user_identifier}",
                    phone=user_identifier,
                    email=None,
                    language=normalized.language or "en",
                )
            elif channel == "email":
                user = User(
                    name=normalized.metadata.get("from_name", "Email User"),
                    email=user_identifier,
                    phone=None,
                    language=normalized.language or "en",
                )
            elif channel == "telegram":
                user = User(
                    name=normalized.metadata.get("first_name", "Telegram User"),
                    email=f"telegram_{user_identifier}",
                    phone=None,
                    language=normalized.language_code or "en",
                )
            else:  # mobile
                # Mobile user should already exist from authentication
                raise ValueError("Mobile user not found")

            session.add(user)
            await session.flush()
            await session.refresh(user)

        return user

    async def _get_or_create_conversation(
        self,
        session: AsyncSession,
        user: User,
        channel: str,
        normalized: NormalizedMessage,
    ) -> Conversation:
        """Get or create conversation for user and channel."""
        # Check if conversation ID is provided
        if normalized.conversation_id:
            result = await session.execute(
                select(Conversation).where(
                    Conversation.id == normalized.conversation_id,
                    Conversation.user_id == user.id,
                )
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                return conversation

        # Try to find active conversation for this user and channel
        channel_enum = ConversationChannel(channel)
        result = await session.execute(
            select(Conversation)
            .where(
                Conversation.user_id == user.id,
                Conversation.channel == channel_enum,
                Conversation.status == "active",
            )
            .order_by(Conversation.started_at.desc())
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            # Create new conversation
            conversation = Conversation(
                user_id=user.id,
                channel=channel_enum,
                status="active",
            )
            session.add(conversation)
            await session.flush()
            await session.refresh(conversation)

        return conversation

    async def _create_message(
        self,
        session: AsyncSession,
        conversation: Conversation,
        normalized: NormalizedMessage,
    ) -> Message:
        """Create message in database."""
        message = Message(
            conversation_id=conversation.id,
            sender_type=normalized.sender_type,
            message=normalized.content or "",
            language=normalized.language,
            metadata=normalized.metadata,
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message

    async def _queue_for_processing(
        self,
        conversation: Conversation,
        message: Message,
        user: User,
        normalized: NormalizedMessage,
    ) -> None:
        """Queue message for AI processing."""
        try:
            from app.services.message_queue import MessageQueueService

            queue = MessageQueueService()

            internal_message = {
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "user_id": str(user.id),
                "message": normalized.content,
                "sender_type": normalized.sender_type,
                "channel": normalized.channel,
                "channel_message_id": normalized.channel_message_id,
                "timestamp": normalized.timestamp.isoformat(),
                "metadata": normalized.metadata,
            }

            await queue.add_to_queue("unified_queue", internal_message)
            logger.info(f"Queued message {message.id} from {normalized.channel} for processing")

        except Exception as e:
            logger.exception(f"Error queuing message for processing: {e}")

    def get_all_health_status(self) -> dict[str, Any]:
        """Get health status of all channel connectors."""
        return {
            channel: connector.get_health_status()
            for channel, connector in self.connectors.items()
        }

    def get_channel_health_status(self, channel: str) -> dict[str, Any]:
        """Get health status of a specific channel connector."""
        connector = self.get_connector(channel)
        return connector.get_health_status()
