"""WhatsApp opt-in and opt-out flow management."""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.models.user import User
from app.schemas.whatsapp import WhatsAppOptStatus, WhatsAppOptStatusResponse
from app.services.whatsapp_client import WhatsAppAPIClient

logger = logging.getLogger(__name__)


class WhatsAppOptService:
    """Service for managing WhatsApp opt-in/opt-out flows."""

    def __init__(self):
        self.client = WhatsAppAPIClient()
        self.opt_out_keywords = {"stop", "unsubscribe", "cancel", "quit", "optout"}
        self.opt_in_keywords = {"start", "subscribe", "yes", "optin"}

    async def handle_opt_in(
        self, phone_number: str, name: str | None = None
    ) -> WhatsAppOptStatusResponse:
        """
        Handle opt-in request from a WhatsApp user.

        Args:
            phone_number: User's WhatsApp phone number
            name: User's name (optional)

        Returns:
            Opt-in status response
        """
        async for session in get_async_session():
            try:
                # Check if user exists by phone number
                result = await session.execute(
                    select(User).where(User.phone == phone_number)
                )
                user = result.scalar_one_or_none()

                if user:
                    # User exists, update opt-in status
                    logger.info(f"Existing user opted in: {phone_number}")
                    # In a real implementation, you might have a separate opt-in table
                    # For now, we'll just log and return success
                    return WhatsAppOptStatusResponse(
                        phone_number=phone_number,
                        status=WhatsAppOptStatus.opted_in,
                        opted_at=datetime.utcnow(),
                        opted_out_at=None,
                    )
                else:
                    # New user, create account
                    logger.info(f"New user opted in: {phone_number}")
                    user = User(
                        name=name or f"WhatsApp User {phone_number[-4:]}",
                        email=f"whatsapp_{phone_number}@temp.local",  # Placeholder email
                        phone=phone_number,
                        language="en",
                    )
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)

                    return WhatsAppOptStatusResponse(
                        phone_number=phone_number,
                        status=WhatsAppOptStatus.opted_in,
                        opted_at=datetime.utcnow(),
                        opted_out_at=None,
                    )

            except Exception as e:
                logger.exception(f"Error handling opt-in for {phone_number}: {e}")
                raise

    async def handle_opt_out(
        self, phone_number: str, reason: str | None = None
    ) -> WhatsAppOptStatusResponse:
        """
        Handle opt-out request from a WhatsApp user.

        Args:
            phone_number: User's WhatsApp phone number
            reason: Reason for opting out (optional)

        Returns:
            Opt-out status response
        """
        async for session in get_async_session():
            try:
                # Find user by phone number
                result = await session.execute(
                    select(User).where(User.phone == phone_number)
                )
                user = result.scalar_one_or_none()

                if user:
                    # User exists, update opt-out status
                    logger.info(f"User opted out: {phone_number}, reason: {reason}")
                    # In a real implementation, you might have a separate opt-in table
                    # For now, we'll just log and return success
                    return WhatsAppOptStatusResponse(
                        phone_number=phone_number,
                        status=WhatsAppOptStatus.opted_out,
                        opted_at=None,
                        opted_out_at=datetime.utcnow(),
                    )
                else:
                    # User doesn't exist
                    logger.warning(f"Opt-out from unknown user: {phone_number}")
                    return WhatsAppOptStatusResponse(
                        phone_number=phone_number,
                        status=WhatsAppOptStatus.opted_out,
                        opted_at=None,
                        opted_out_at=datetime.utcnow(),
                    )

            except Exception as e:
                logger.exception(f"Error handling opt-out for {phone_number}: {e}")
                raise

    async def check_opt_status(self, phone_number: str) -> WhatsAppOptStatusResponse:
        """
        Check the opt-in/opt-out status of a WhatsApp user.

        Args:
            phone_number: User's WhatsApp phone number

        Returns:
            Current opt status
        """
        async for session in get_async_session():
            try:
                # Find user by phone number
                result = await session.execute(
                    select(User).where(User.phone == phone_number)
                )
                user = result.scalar_one_or_none()

                if user:
                    # User exists - assume opted in
                    # In a real implementation, check a separate opt-in table
                    return WhatsAppOptStatusResponse(
                        phone_number=phone_number,
                        status=WhatsAppOptStatus.opted_in,
                        opted_at=user.created_at,
                        opted_out_at=None,
                    )
                else:
                    # User doesn't exist - assume opted out
                    return WhatsAppOptStatusResponse(
                        phone_number=phone_number,
                        status=WhatsAppOptStatus.opted_out,
                        opted_at=None,
                        opted_out_at=None,
                    )

            except Exception as e:
                logger.exception(f"Error checking opt status for {phone_number}: {e}")
                raise

    async def send_opt_in_confirmation(self, phone_number: str) -> None:
        """
        Send opt-in confirmation message via WhatsApp.

        Args:
            phone_number: User's WhatsApp phone number
        """
        try:
            message = (
                "✅ You have successfully opted in to receive messages from us.\n\n"
                "Reply STOP at any time to opt out."
            )
            await self.client.send_text_message(to=phone_number, text=message)
            logger.info(f"Sent opt-in confirmation to {phone_number}")
        except Exception as e:
            logger.exception(f"Error sending opt-in confirmation: {e}")

    async def send_opt_out_confirmation(self, phone_number: str) -> None:
        """
        Send opt-out confirmation message via WhatsApp.

        Args:
            phone_number: User's WhatsApp phone number
        """
        try:
            message = (
                "❌ You have been opted out. You will no longer receive messages from us.\n\n"
                "Reply START at any time to opt back in."
            )
            await self.client.send_text_message(to=phone_number, text=message)
            logger.info(f"Sent opt-out confirmation to {phone_number}")
        except Exception as e:
            logger.exception(f"Error sending opt-out confirmation: {e}")

    async def process_opt_keyword(
        self, phone_number: str, message_content: str
    ) -> tuple[bool, str]:
        """
        Process a message to check if it contains opt-in/opt-out keywords.

        Args:
            phone_number: User's WhatsApp phone number
            message_content: Message content to check

        Returns:
            Tuple of (was_opt_action, action_type)
        """
        content_lower = message_content.lower().strip()

        if content_lower in self.opt_out_keywords:
            await self.handle_opt_out(phone_number)
            await self.send_opt_out_confirmation(phone_number)
            return True, "opt_out"
        elif content_lower in self.opt_in_keywords:
            await self.handle_opt_in(phone_number)
            await self.send_opt_in_confirmation(phone_number)
            return True, "opt_in"

        return False, ""

    async def send_opt_in_template(
        self, phone_number: str, template_name: str = "opt_in_confirmation"
    ) -> None:
        """
        Send opt-in confirmation using a template message.

        Args:
            phone_number: User's WhatsApp phone number
            template_name: Name of the template to use
        """
        try:
            from app.services.whatsapp_templates import WhatsAppTemplateService

            template_service = WhatsAppTemplateService()

            # Build template components
            components = [
                {
                    "type": "BODY",
                    "text": "You have successfully opted in to receive messages from us. Reply STOP at any time to opt out.",
                }
            ]

            await template_service.client.send_template_message(
                to=phone_number,
                template_name=template_name,
                components=components,
                language_code="en_US",
            )
            logger.info(f"Sent opt-in template to {phone_number}")
        except Exception as e:
            logger.exception(f"Error sending opt-in template: {e}")
            # Fallback to text message
            await self.send_opt_in_confirmation(phone_number)

    async def send_opt_out_template(
        self, phone_number: str, template_name: str = "opt_out_confirmation"
    ) -> None:
        """
        Send opt-out confirmation using a template message.

        Args:
            phone_number: User's WhatsApp phone number
            template_name: Name of the template to use
        """
        try:
            from app.services.whatsapp_templates import WhatsAppTemplateService

            template_service = WhatsAppTemplateService()

            # Build template components
            components = [
                {
                    "type": "BODY",
                    "text": "You have been opted out. You will no longer receive messages from us. Reply START at any time to opt back in.",
                }
            ]

            await template_service.client.send_template_message(
                to=phone_number,
                template_name=template_name,
                components=components,
                language_code="en_US",
            )
            logger.info(f"Sent opt-out template to {phone_number}")
        except Exception as e:
            logger.exception(f"Error sending opt-out template: {e}")
            # Fallback to text message
            await self.send_opt_out_confirmation(phone_number)
