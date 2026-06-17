"""Email thread detection and conversation linking service."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.models.conversation import Conversation, ConversationChannel
from app.models.message import Message
from app.models.user import User
from app.schemas.email import EmailThreadInfo, ParsedEmailMessage

logger = logging.getLogger(__name__)


class EmailThreadService:
    """Service for detecting email threads and linking to conversations."""

    async def detect_thread(
        self, parsed_email: ParsedEmailMessage
    ) -> EmailThreadInfo:
        """
        Detect email thread and link to existing conversation.

        Args:
            parsed_email: Parsed email message

        Returns:
            Thread information with conversation ID
        """
        async for session in get_async_session():
            try:
                # Check if this is a reply to an existing message
                if parsed_email.is_reply and parsed_email.in_reply_to:
                    conversation_id = await self._find_conversation_by_message_id(
                        session, parsed_email.in_reply_to
                    )
                    if conversation_id:
                        return EmailThreadInfo(
                            thread_id=parsed_email.thread_id,
                            message_count=0,  # Will be updated
                            first_message_id=parsed_email.in_reply_to,
                            last_message_id=parsed_email.message_id,
                            conversation_id=conversation_id,
                        )

                # Check if there's an existing conversation with this email
                conversation_id = await self._find_conversation_by_email(
                    session, parsed_email.from_email
                )
                if conversation_id:
                    return EmailThreadInfo(
                        thread_id=parsed_email.thread_id,
                        message_count=0,
                        first_message_id=parsed_email.message_id,
                        last_message_id=parsed_email.message_id,
                        conversation_id=conversation_id,
                    )

                # Create new conversation
                conversation_id = await self._create_conversation(
                    session, parsed_email
                )
                return EmailThreadInfo(
                    thread_id=parsed_email.thread_id,
                    message_count=1,
                    first_message_id=parsed_email.message_id,
                    last_message_id=parsed_email.message_id,
                    conversation_id=conversation_id,
                )

            except Exception as e:
                logger.exception(f"Error detecting email thread: {e}")
                raise

    async def _find_conversation_by_message_id(
        self, session: AsyncSession, message_id: str
    ) -> UUID | None:
        """Find conversation by email message ID stored in message metadata."""
        try:
            # Search for message with matching email message ID in metadata
            result = await session.execute(
                select(Message).where(
                    Message.message.contains(message_id)
                )
            )
            message = result.scalar_one_or_none()

            if message:
                return message.conversation_id

            return None

        except Exception as e:
            logger.error(f"Error finding conversation by message ID: {e}")
            return None

    async def _find_conversation_by_email(
        self, session: AsyncSession, email: str
    ) -> UUID | None:
        """Find existing conversation for this email address."""
        try:
            # Find user by email
            result = await session.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()

            if not user:
                return None

            # Find active conversation for this user on email channel
            result = await session.execute(
                select(Conversation)
                .where(
                    Conversation.user_id == user.id,
                    Conversation.channel == ConversationChannel.email,
                    Conversation.status == "active",
                )
                .order_by(Conversation.started_at.desc())
            )
            conversation = result.scalar_one_or_none()

            if conversation:
                return conversation.id

            return None

        except Exception as e:
            logger.error(f"Error finding conversation by email: {e}")
            return None

    async def _create_conversation(
        self, session: AsyncSession, parsed_email: ParsedEmailMessage
    ) -> UUID:
        """Create new conversation for email."""
        try:
            # Find or create user
            result = await session.execute(
                select(User).where(User.email == parsed_email.from_email)
            )
            user = result.scalar_one_or_none()

            if not user:
                # Create new user
                user = User(
                    name=parsed_email.from_name or "Email User",
                    email=parsed_email.from_email,
                    phone=None,
                    language="en",
                )
                session.add(user)
                await session.flush()
                await session.refresh(user)

            # Create new conversation
            conversation = Conversation(
                user_id=user.id,
                channel=ConversationChannel.email,
                status="active",
            )
            session.add(conversation)
            await session.flush()
            await session.refresh(conversation)

            logger.info(
                f"Created new conversation {conversation.id} for email {parsed_email.from_email}"
            )

            return conversation.id

        except Exception as e:
            logger.exception(f"Error creating conversation: {e}")
            raise

    async def link_message_to_conversation(
        self,
        session: AsyncSession,
        conversation_id: UUID,
        parsed_email: ParsedEmailMessage,
    ) -> UUID:
        """
        Link email message to conversation.

        Args:
            session: Database session
            conversation_id: Conversation ID
            parsed_email: Parsed email message

        Returns:
            Message ID
        """
        try:
            # Create message record
            message = Message(
                conversation_id=conversation_id,
                sender_type="customer",
                message=parsed_email.extracted_body,
                language="en",
            )
            session.add(message)
            await session.flush()
            await session.refresh(message)

            # Store email metadata in message (could use JSONB field or separate table)
            # For now, we'll store the message ID in the message text for reference
            # In production, you'd want a proper metadata table

            logger.info(
                f"Linked email message {parsed_email.message_id} to conversation {conversation_id}"
            )

            return message.id

        except Exception as e:
            logger.exception(f"Error linking message to conversation: {e}")
            raise

    async def get_thread_messages(
        self, conversation_id: UUID, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get messages in a thread for context.

        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages to return

        Returns:
            List of messages
        """
        async for session in get_async_session():
            try:
                result = await session.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.timestamp.desc())
                    .limit(limit)
                )
                messages = result.scalars().all()

                return [
                    {
                        "id": str(msg.id),
                        "sender_type": msg.sender_type,
                        "message": msg.message,
                        "timestamp": msg.timestamp.isoformat(),
                    }
                    for msg in reversed(messages)
                ]

            except Exception as e:
                logger.exception(f"Error getting thread messages: {e}")
                raise
