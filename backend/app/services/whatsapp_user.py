"""WhatsApp user service for handling phone number as identifier."""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.models.user import User

logger = logging.getLogger(__name__)


class WhatsAppUserService:
    """Service for managing WhatsApp users using phone numbers as identifiers."""

    async def get_or_create_user_by_phone(
        self, phone_number: str, name: str | None = None
    ) -> User:
        """
        Get existing user by phone number or create a new one.

        Args:
            phone_number: WhatsApp phone number (E164 format)
            name: User's name (optional)

        Returns:
            User instance
        """
        async for session in get_async_session():
            try:
                # Try to find existing user by phone
                result = await session.execute(
                    select(User).where(User.phone == phone_number)
                )
                user = result.scalar_one_or_none()

                if user:
                    logger.info(f"Found existing user by phone: {phone_number}")
                    # Update name if provided and current name is generic
                    if name and user.name.startswith("WhatsApp User"):
                        user.name = name
                        await session.commit()
                        await session.refresh(user)
                    return user

                # Create new user
                logger.info(f"Creating new user for phone: {phone_number}")
                user = User(
                    name=name or f"WhatsApp User {phone_number[-4:]}",
                    email=None,  # Email not required for WhatsApp users
                    phone=phone_number,
                    language="en",
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return user

            except Exception as e:
                logger.exception(f"Error getting/creating user by phone: {e}")
                raise

    async def get_user_by_phone(self, phone_number: str) -> User | None:
        """
        Get user by phone number.

        Args:
            phone_number: WhatsApp phone number

        Returns:
            User instance or None
        """
        async for session in get_async_session():
            try:
                result = await session.execute(
                    select(User).where(User.phone == phone_number)
                )
                return result.scalar_one_or_none()
            except Exception as e:
                logger.exception(f"Error getting user by phone: {e}")
                raise

    async def update_user_name(self, phone_number: str, name: str) -> User | None:
        """
        Update user's name.

        Args:
            phone_number: WhatsApp phone number
            name: New name

        Returns:
            Updated user or None
        """
        async for session in get_async_session():
            try:
                result = await session.execute(
                    select(User).where(User.phone == phone_number)
                )
                user = result.scalar_one_or_none()

                if user:
                    user.name = name
                    await session.commit()
                    await session.refresh(user)
                    return user

                return None

            except Exception as e:
                logger.exception(f"Error updating user name: {e}")
                raise

    async def link_email_to_phone(
        self, phone_number: str, email: str
    ) -> User | None:
        """
        Link an email address to a WhatsApp user.

        Args:
            phone_number: WhatsApp phone number
            email: Email address to link

        Returns:
            Updated user or None
        """
        async for session in get_async_session():
            try:
                result = await session.execute(
                    select(User).where(User.phone == phone_number)
                )
                user = result.scalar_one_or_none()

                if user:
                    user.email = email
                    await session.commit()
                    await session.refresh(user)
                    return user

                return None

            except Exception as e:
                logger.exception(f"Error linking email to phone: {e}")
                raise

    async def get_user_conversation_count(self, phone_number: str) -> int:
        """
        Get the number of conversations for a user.

        Args:
            phone_number: WhatsApp phone number

        Returns:
            Number of conversations
        """
        async for session in get_async_session():
            try:
                result = await session.execute(
                    select(User).where(User.phone == phone_number)
                )
                user = result.scalar_one_or_none()

                if user:
                    return len(user.conversations)

                return 0

            except Exception as e:
                logger.exception(f"Error getting conversation count: {e}")
                raise
