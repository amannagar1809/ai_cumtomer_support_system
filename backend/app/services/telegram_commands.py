"""Telegram bot command handlers."""

import logging
from typing import Any

from app.services.telegram_client import TelegramBotClient
from app.services.telegram_keyboards import TelegramKeyboardBuilder
from app.services.telegram_user import TelegramUserService

logger = logging.getLogger(__name__)


class TelegramCommandHandler:
    """Handler for Telegram bot commands."""

    def __init__(self):
        self.client = TelegramBotClient()
        self.user_service = TelegramUserService()
        self.keyboard_builder = TelegramKeyboardBuilder()

    async def handle_start(self, chat_id: int, telegram_user_id: int, first_name: str) -> str:
        """
        Handle /start command.

        Args:
            chat_id: Telegram chat ID
            telegram_user_id: Telegram user ID
            first_name: User's first name

        Returns:
            Response message
        """
        try:
            # Create or get user
            await self.user_service.get_or_create_user(
                telegram_user_id=telegram_user_id,
                first_name=first_name,
            )

            # Send welcome message
            welcome_message = (
                f"👋 Welcome, {first_name}!\n\n"
                "I'm your AI Customer Support assistant. "
                "I'm here to help you with any questions or issues you may have.\n\n"
                "You can:\n"
                "• Send me a message to start a conversation\n"
                "• Use /help to see available commands\n"
                "• Use /ticket to create a support ticket\n"
                "• Use /status to check your ticket status"
            )

            # Send with main menu keyboard
            keyboard = self.keyboard_builder.build_main_menu_keyboard()
            await self.client.send_message(
                chat_id=chat_id,
                text=welcome_message,
                reply_markup=keyboard,
            )

            return "start_handled"

        except Exception as e:
            logger.exception(f"Error handling /start command: {e}")
            raise

    async def handle_help(self, chat_id: int) -> str:
        """
        Handle /help command.

        Args:
            chat_id: Telegram chat ID

        Returns:
            Response message
        """
        try:
            help_message = (
                "📚 *Available Commands*\n\n"
                "/start - Start the bot and see welcome message\n"
                "/help - Show this help message\n"
                "/ticket - Create a new support ticket\n"
                "/status - Check your ticket status\n\n"
                "*Quick Actions*\n\n"
                "You can also:\n"
                "• Send any text message to chat with AI\n"
                "• Send photos, documents, or voice messages\n"
                "• Use inline buttons for quick actions\n\n"
                "Need more help? Just ask!"
            )

            await self.client.send_message(
                chat_id=chat_id,
                text=help_message,
                parse_mode="Markdown",
            )

            return "help_handled"

        except Exception as e:
            logger.exception(f"Error handling /help command: {e}")
            raise

    async def handle_ticket(self, chat_id: int, telegram_user_id: int) -> str:
        """
        Handle /ticket command.

        Args:
            chat_id: Telegram chat ID
            telegram_user_id: Telegram user ID

        Returns:
            Response message
        """
        try:
            # Get user's conversation
            conversation = await self.user_service.get_conversation(
                telegram_user_id, chat_id
            )

            if not conversation:
                # Create new conversation
                conversation = await self.user_service.create_conversation(
                    telegram_user_id, chat_id
                )

            ticket_message = (
                "🎫 *Create Support Ticket*\n\n"
                "To create a ticket, please provide:\n\n"
                "1. A brief description of your issue\n"
                "2. Category (Technical, Billing, Product, Account)\n"
                "3. Priority (High, Medium, Low)\n\n"
                "Or use the quick options below:"
            )

            keyboard = self.keyboard_builder.build_category_keyboard()
            await self.client.send_message(
                chat_id=chat_id,
                text=ticket_message,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )

            return "ticket_initiated"

        except Exception as e:
            logger.exception(f"Error handling /ticket command: {e}")
            raise

    async def handle_status(self, chat_id: int, telegram_user_id: int) -> str:
        """
        Handle /status command.

        Args:
            chat_id: Telegram chat ID
            telegram_user_id: Telegram user ID

        Returns:
            Response message
        """
        try:
            # Get user
            user = await self.user_service.get_user_by_telegram_id(telegram_user_id)
            if not user:
                await self.client.send_message(
                    chat_id=chat_id,
                    text="❌ User not found. Please use /start to register.",
                )
                return "user_not_found"

            # Get conversation
            conversation = await self.user_service.get_conversation(
                telegram_user_id, chat_id
            )

            if not conversation:
                await self.client.send_message(
                    chat_id=chat_id,
                    text="📋 No active conversation found. Start a new conversation to create tickets.",
                )
                return "no_conversation"

            # In a real implementation, you would query the ticket service
            # For now, we'll send a placeholder response
            status_message = (
                f"📋 *Ticket Status*\n\n"
                f"Conversation ID: `{conversation.id}`\n"
                f"Status: {conversation.status}\n"
                f"Started: {conversation.started_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                "To view specific tickets, please provide a ticket ID or use the menu below."
            )

            keyboard = self.keyboard_builder.build_ticket_options_keyboard()
            await self.client.send_message(
                chat_id=chat_id,
                text=status_message,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )

            return "status_shown"

        except Exception as e:
            logger.exception(f"Error handling /status command: {e}")
            raise

    async def handle_callback_query(
        self, callback_query_id: str, callback_data: str, chat_id: int
    ) -> str:
        """
        Handle callback query from inline keyboard.

        Args:
            callback_query_id: Callback query ID
            callback_data: Callback data string
            chat_id: Telegram chat ID

        Returns:
            Response action
        """
        try:
            # Answer the callback query
            await self.client.answer_callback_query(callback_query_id)

            # Handle different callback data
            if callback_data == "create_ticket":
                return await self.handle_ticket(chat_id, 0)  # Will need user ID
            elif callback_data == "view_tickets":
                await self.client.send_message(
                    chat_id=chat_id,
                    text="📋 Your tickets will be displayed here.",
                )
            elif callback_data == "check_status":
                await self.client.send_message(
                    chat_id=chat_id,
                    text="🔍 Status check feature coming soon!",
                )
            elif callback_data == "chat_ai":
                await self.client.send_message(
                    chat_id=chat_id,
                    text="💬 You can now chat with AI. Just send me a message!",
                )
            elif callback_data.startswith("category_"):
                category = callback_data.replace("category_", "")
                await self.client.send_message(
                    chat_id=chat_id,
                    text=f"✅ Category selected: {category}\n\nNow select priority:",
                    reply_markup=self.keyboard_builder.build_priority_keyboard(),
                )
            elif callback_data.startswith("priority_"):
                priority = callback_data.replace("priority_", "")
                await self.client.send_message(
                    chat_id=chat_id,
                    text=f"✅ Priority selected: {priority}\n\nPlease describe your issue:",
                )
            elif callback_data == "back":
                await self.client.send_message(
                    chat_id=chat_id,
                    text="🔙 Going back...",
                    reply_markup=self.keyboard_builder.build_main_menu_keyboard(),
                )
            elif callback_data == "yes":
                await self.client.send_message(
                    chat_id=chat_id,
                    text="✅ You selected Yes",
                )
            elif callback_data == "no":
                await self.client.send_message(
                    chat_id=chat_id,
                    text="❌ You selected No",
                )
            else:
                await self.client.send_message(
                    chat_id=chat_id,
                    text=f"Unknown action: {callback_data}",
                )

            return f"callback_{callback_data}"

        except Exception as e:
            logger.exception(f"Error handling callback query: {e}")
            raise

    async def register_commands(self) -> None:
        """Register bot commands with Telegram."""
        try:
            commands = [
                {"command": "start", "description": "Start the bot"},
                {"command": "help", "description": "Show help message"},
                {"command": "ticket", "description": "Create a support ticket"},
                {"command": "status", "description": "Check ticket status"},
            ]

            await self.client.set_bot_commands(commands)
            logger.info("Bot commands registered successfully")

        except Exception as e:
            logger.exception(f"Error registering bot commands: {e}")
