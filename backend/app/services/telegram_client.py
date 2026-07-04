"""Telegram Bot API client for sending messages and managing bot."""

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.telegram import (
    TelegramBotInfo,
    TelegramSendMessageRequest,
    TelegramSendMessageResponse,
    TelegramSendPhotoRequest,
    TelegramSendDocumentRequest,
)

logger = logging.getLogger(__name__)


class TelegramBotClient:
    """Client for interacting with Telegram Bot API."""

    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
        self.timeout = 30.0

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict[str, Any] | None = None,
        reply_to_message_id: int | None = None,
    ) -> TelegramSendMessageResponse:
        """
        Send a text message via Telegram Bot API.

        Args:
            chat_id: Chat ID to send message to
            text: Message text
            parse_mode: Parse mode (Markdown, HTML)
            reply_markup: Inline keyboard or reply keyboard
            reply_to_message_id: Message ID to reply to

        Returns:
            API response
        """
        if not settings.telegram_enabled:
            logger.warning("Telegram is not enabled")
            raise ValueError("Telegram is not enabled")

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": reply_markup,
            "reply_to_message_id": reply_to_message_id,
        }

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return TelegramSendMessageResponse(**result)

    async def send_photo(
        self,
        chat_id: int | str,
        photo: str,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> TelegramSendMessageResponse:
        """
        Send a photo via Telegram Bot API.

        Args:
            chat_id: Chat ID to send photo to
            photo: Photo file_id or URL
            caption: Photo caption
            parse_mode: Parse mode for caption
            reply_markup: Inline keyboard

        Returns:
            API response
        """
        if not settings.telegram_enabled:
            logger.warning("Telegram is not enabled")
            raise ValueError("Telegram is not enabled")

        url = f"{self.base_url}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": photo,
            "caption": caption,
            "parse_mode": parse_mode,
            "reply_markup": reply_markup,
        }

        payload = {k: v for k, v in payload.items() if v is not None}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return TelegramSendMessageResponse(**result)

    async def send_document(
        self,
        chat_id: int | str,
        document: str,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> TelegramSendMessageResponse:
        """
        Send a document via Telegram Bot API.

        Args:
            chat_id: Chat ID to send document to
            document: Document file_id or URL
            caption: Document caption
            parse_mode: Parse mode for caption
            reply_markup: Inline keyboard

        Returns:
            API response
        """
        if not settings.telegram_enabled:
            logger.warning("Telegram is not enabled")
            raise ValueError("Telegram is not enabled")

        url = f"{self.base_url}/sendDocument"
        payload = {
            "chat_id": chat_id,
            "document": document,
            "caption": caption,
            "parse_mode": parse_mode,
            "reply_markup": reply_markup,
        }

        payload = {k: v for k, v in payload.items() if v is not None}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return TelegramSendMessageResponse(**result)

    async def get_file(self, file_id: str) -> dict[str, Any]:
        """
        Get file information and download URL.

        Args:
            file_id: File ID

        Returns:
            File information with file_path
        """
        if not settings.telegram_enabled:
            logger.warning("Telegram is not enabled")
            raise ValueError("Telegram is not enabled")

        url = f"{self.base_url}/getFile"
        payload = {"file_id": file_id}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    async def download_file(self, file_path: str) -> bytes:
        """
        Download file from Telegram servers.

        Args:
            file_path: File path from getFile response

        Returns:
            File content as bytes
        """
        if not settings.telegram_enabled:
            logger.warning("Telegram is not enabled")
            raise ValueError("Telegram is not enabled")

        url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def set_webhook(self, webhook_url: str, secret_token: str | None = None) -> dict[str, Any]:
        """
        Set webhook for Telegram bot.

        Args:
            webhook_url: Webhook URL
            secret_token: Optional secret token for verification

        Returns:
            API response
        """
        if not settings.telegram_enabled:
            logger.warning("Telegram is not enabled")
            raise ValueError("Telegram is not enabled")

        url = f"{self.base_url}/setWebhook"
        payload = {"url": webhook_url}
        if secret_token:
            payload["secret_token"] = secret_token

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    async def delete_webhook(self) -> dict[str, Any]:
        """Delete webhook for Telegram bot."""
        if not settings.telegram_enabled:
            logger.warning("Telegram is not enabled")
            raise ValueError("Telegram is not enabled")

        url = f"{self.base_url}/deleteWebhook"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url)
            response.raise_for_status()
            return response.json()

    async def get_webhook_info(self) -> dict[str, Any]:
        """Get current webhook information."""
        if not settings.telegram_enabled:
            logger.warning("Telegram is not enabled")
            raise ValueError("Telegram is not enabled")

        url = f"{self.base_url}/getWebhookInfo"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def get_bot_info(self) -> TelegramBotInfo:
        """Get bot information."""
        if not settings.telegram_enabled:
            logger.warning("Telegram is not enabled")
            raise ValueError("Telegram is not enabled")

        url = f"{self.base_url}/getMe"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            result = response.json()
            return TelegramBotInfo(**result["result"])

    async def set_bot_commands(self, commands: list[dict[str, str]]) -> dict[str, Any]:
        """
        Set bot commands.

        Args:
            commands: List of command dictionaries with 'command' and 'description'

        Returns:
            API response
        """
        if not settings.telegram_enabled:
            logger.warning("Telegram is not enabled")
            raise ValueError("Telegram is not enabled")

        url = f"{self.base_url}/setMyCommands"
        payload = {"commands": commands}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> dict[str, Any]:
        """
        Answer a callback query from inline keyboard.

        Args:
            callback_query_id: Callback query ID
            text: Optional text to show
            show_alert: Whether to show as alert

        Returns:
            API response
        """
        if not settings.telegram_enabled:
            logger.warning("Telegram is not enabled")
            raise ValueError("Telegram is not enabled")

        url = f"{self.base_url}/answerCallbackQuery"
        payload = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
        }

        payload = {k: v for k, v in payload.items() if v is not None}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
