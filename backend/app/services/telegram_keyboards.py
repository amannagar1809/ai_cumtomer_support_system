"""Telegram inline keyboard builder for quick replies."""

import logging
from typing import Any

from app.schemas.telegram import (
    TelegramInlineKeyboardButton,
    TelegramInlineKeyboardMarkup,
)

logger = logging.getLogger(__name__)


class TelegramKeyboardBuilder:
    """Builder for creating Telegram inline keyboards."""

    def build_inline_keyboard(
        self, buttons: list[list[dict[str, Any]]]
    ) -> dict[str, Any]:
        """
        Build inline keyboard markup.

        Args:
            buttons: 2D array of button configurations

        Returns:
            Inline keyboard markup dictionary
        """
        inline_keyboard = []
        for row in buttons:
            keyboard_row = []
            for button in row:
                keyboard_row.append(
                    TelegramInlineKeyboardButton(
                        text=button.get("text", ""),
                        callback_data=button.get("callback_data"),
                        url=button.get("url"),
                    )
                )
            inline_keyboard.append(keyboard_row)

        return TelegramInlineKeyboardMarkup(inline_keyboard=inline_keyboard).model_dump()

    def build_quick_reply_keyboard(self, options: list[str]) -> dict[str, Any]:
        """
        Build quick reply keyboard with text options.

        Args:
            options: List of text options

        Returns:
            Reply keyboard markup
        """
        keyboard = [[{"text": option}] for option in options]
        return {
            "keyboard": keyboard,
            "resize_keyboard": True,
            "one_time_keyboard": False,
            "selective": True,
        }

    def build_yes_no_keyboard(self) -> dict[str, Any]:
        """Build a Yes/No inline keyboard."""
        buttons = [
            [
                {"text": "✅ Yes", "callback_data": "yes"},
                {"text": "❌ No", "callback_data": "no"},
            ]
        ]
        return self.build_inline_keyboard(buttons)

    def build_ticket_options_keyboard(self) -> dict[str, Any]:
        """Build keyboard for ticket options."""
        buttons = [
            [
                {"text": "🎫 Create Ticket", "callback_data": "create_ticket"},
                {"text": "📋 View Tickets", "callback_data": "view_tickets"},
            ],
            [
                {"text": "🔍 Check Status", "callback_data": "check_status"},
                {"text": "💬 Chat with AI", "callback_data": "chat_ai"},
            ],
        ]
        return self.build_inline_keyboard(buttons)

    def build_category_keyboard(self) -> dict[str, Any]:
        """Build keyboard for ticket category selection."""
        buttons = [
            [
                {"text": "💻 Technical", "callback_data": "category_technical"},
                {"text": "💰 Billing", "callback_data": "category_billing"},
            ],
            [
                {"text": "📦 Product", "callback_data": "category_product"},
                {"text": "👤 Account", "callback_data": "category_account"},
            ],
            [
                {"text": "🔙 Back", "callback_data": "back"},
            ],
        ]
        return self.build_inline_keyboard(buttons)

    def build_priority_keyboard(self) -> dict[str, Any]:
        """Build keyboard for priority selection."""
        buttons = [
            [
                {"text": "🔴 High", "callback_data": "priority_high"},
                {"text": "🟡 Medium", "callback_data": "priority_medium"},
            ],
            [
                {"text": "🟢 Low", "callback_data": "priority_low"},
                {"text": "🔙 Back", "callback_data": "back"},
            ],
        ]
        return self.build_inline_keyboard(buttons)

    def build_main_menu_keyboard(self) -> dict[str, Any]:
        """Build main menu keyboard."""
        buttons = [
            [
                {"text": "🆕 New Conversation", "callback_data": "new_conversation"},
                {"text": "📋 My Tickets", "callback_data": "my_tickets"},
            ],
            [
                {"text": "❓ Help", "callback_data": "help"},
                {"text": "⚙️ Settings", "callback_data": "settings"},
            ],
        ]
        return self.build_inline_keyboard(buttons)

    def build_rating_keyboard(self) -> dict[str, Any]:
        """Build rating keyboard (1-5 stars)."""
        buttons = [
            [
                {"text": "⭐", "callback_data": "rating_1"},
                {"text": "⭐⭐", "callback_data": "rating_2"},
                {"text": "⭐⭐⭐", "callback_data": "rating_3"},
            ],
            [
                {"text": "⭐⭐⭐⭐", "callback_data": "rating_4"},
                {"text": "⭐⭐⭐⭐⭐", "callback_data": "rating_5"},
            ],
        ]
        return self.build_inline_keyboard(buttons)

    def build_continue_keyboard(self) -> dict[str, Any]:
        """Build keyboard for continue conversation option."""
        buttons = [
            [
                {"text": "▶️ Continue", "callback_data": "continue"},
                {"text": "🆕 New Topic", "callback_data": "new_topic"},
            ],
        ]
        return self.build_inline_keyboard(buttons)
