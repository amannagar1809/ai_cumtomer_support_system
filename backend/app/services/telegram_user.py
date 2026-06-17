"""Telegram user service for mapping Telegram user ID to internal user ID."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.models.conversation import Conversation, ConversationChannel
from app.models.user import User

logger = logging.getLogger(__name__)


class TelegramUserService:
    """Service for managing Telegram users and mapping to internal user IDs."""

    async def get_or_create_user(
        self,
        telegram_user_id: int,
        username: str | None = None,
        first_name: str = "",
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> User:
        """
        Get existing user by Telegram user ID or create a new one.

        Args:
            telegram_user_id: Telegram user ID
            username: Telegram username
            first_name: User's first name
            last_name: User's last name
            language_code: User's language code

        Returns:
            User instance
        """
        async for session in get_async_session():
            try:
                # Try to find existing user by Telegram user ID (stored in email field for simplicity)
                # In production, you'd want a separate telegram_user_id field
                result = await session.execute(
                    select(User).where(User.email == f"telegram_{telegram_user_id}")
                )
                user = result.scalar_one_or_none()

                if user:
                    logger.info(f"Found existing user for Telegram ID: {telegram_user_id}")
                    # Update user info if needed
                    if username and not user.name.startswith("Telegram User"):
                        user.name = f"{first_name} {last_name or ''}".strip()
                    await session.commit()
                    await session.refresh(user)
                    return user

                # Create new user
                logger.info(f"Creating new user for Telegram ID: {telegram_user_id}")
                user = User(
                    name=f"{first_name} {last_name or ''}".strip() or f"Telegram User {telegram_user_id}",
                    email=f"telegram_{telegram_user_id}",  # Use email field to store Telegram ID
                    phone=None,
                    language=language_code or "en",
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return user

            except Exception as e:
                logger.exception(f"Error getting/creating user by Telegram ID: {e}")
                raise

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        """
        Get user by Telegram user ID.

        Args:
            telegram_user_id: Telegram user ID

        Returns:
            User instance or None
        """
        async for session in get_async_session():
            try:
                result = await session.execute(
                    select(User).where(User.email == f"telegram_{telegram_user_id}")
                )
                return result.scalar_one_or_none()
            except Exception as e:
                logger.exception(f"Error getting user by Telegram ID: {e}")
                raise

    async def get_conversation(
        self, telegram_user_id: int, telegram_chat_id: int
    ) -> Conversation | None:
        """
        Get existing conversation for Telegram user.

        Args:
            telegram_user_id: Telegram user ID
            telegram_chat_id: Telegram chat ID

        Returns:
            Conversation instance or None
        """
        async for session in get_async_session():
            try:
                # Get user
                user = await self.get_user_by_telegram_id(telegram_user_id)
                if not user:
                    return None

                # Find active conversation for this user on Telegram channel
                result = await session.execute(
                    select(Conversation)
                    .where(
                        Conversation.user_id == user.id,
                        Conversation.channel == ConversationChannel.telegram,
                        Conversation.status == "active",
                    )
                    .order_by(Conversation.started_at.desc())
                )
                conversation = result.scalar_one_or_none()

                return conversation

            except Exception as e:
                logger.exception(f"Error getting conversation: {e}")
                raise

    async def create_conversation(
        self, telegram_user_id: int, telegram_chat_id: int
    ) -> Conversation:
        """
        Create new conversation for Telegram user.

        Args:
            telegram_user_id: Telegram user ID
            telegram_chat_id: Telegram chat ID

        Returns:
            Conversation instance
        """
        async for session in get_async_session():
            try:
                # Get or create user
                user = await self.get_or_create_user(telegram_user_id)

                # Create new conversation
                conversation = Conversation(
                    user_id=user.id,
                    channel=ConversationChannel.telegram,
                    status="active",
                )
                session.add(conversation)
                await session.commit()
                await session.refresh(conversation)

                logger.info(
                    f"Created new conversation {conversation.id} for Telegram user {telegram_user_id}"
                )

                return conversation

            except Exception as e:
                logger.exception(f"Error creating conversation: {e}")
                raise
