"""WhatsApp Business API client for sending messages."""

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.whatsapp import (
    WhatsAppMediaMessage,
    WhatsAppSendMessageRequest,
    WhatsAppSendMessageResponse,
    WhatsAppTemplateMessage,
    WhatsAppTextMessage,
)

logger = logging.getLogger(__name__)


class WhatsAppAPIClient:
    """Client for interacting with WhatsApp Business API."""

    def __init__(self):
        self.base_url = f"https://graph.facebook.com/{settings.whatsapp_api_version}"
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.access_token = settings.whatsapp_access_token
        self.timeout = 30.0

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def send_text_message(
        self, to: str, text: str, preview_url: bool = False
    ) -> dict[str, Any]:
        """
        Send a text message via WhatsApp API.

        Args:
            to: Recipient phone number (with country code, no + or spaces)
            text: Message content
            preview_url: Whether to generate link previews

        Returns:
            API response
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = self._get_headers()

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": preview_url},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def send_template_message(
        self, to: str, template_name: str, components: list[dict[str, Any]], language_code: str = "en_US"
    ) -> dict[str, Any]:
        """
        Send a template message via WhatsApp API.

        Args:
            to: Recipient phone number
            template_name: Name of the approved template
            components: Template components (body, header, buttons)
            language_code: Language code for the template

        Returns:
            API response
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = self._get_headers()

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def send_media_message(
        self,
        to: str,
        media_type: str,
        media_id: str | None = None,
        url: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """
        Send a media message via WhatsApp API.

        Args:
            to: Recipient phone number
            media_type: Type of media (image, document, audio, video)
            media_id: Media ID from upload
            url: Media URL
            caption: Optional caption

        Returns:
            API response
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        if not media_id and not url:
            raise ValueError("Either media_id or url must be provided")

        url_endpoint = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = self._get_headers()

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": media_type,
            media_type: {},
        }

        if media_id:
            payload[media_type]["id"] = media_id
        if url:
            payload[media_type]["link"] = url
        if caption:
            payload[media_type]["caption"] = caption

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url_endpoint, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def upload_media(self, file_path: str) -> dict[str, Any]:
        """
        Upload media to WhatsApp servers.

        Args:
            file_path: Path to the file to upload

        Returns:
            API response with media ID
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        url = f"{self.base_url}/{self.phone_number_id}/media"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }

        with open(file_path, "rb") as f:
            files = {"file": f}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, files=files)
                response.raise_for_status()
                return response.json()

    async def get_media_url(self, media_id: str) -> dict[str, Any]:
        """
        Get the download URL for a media file.

        Args:
            media_id: ID of the media file

        Returns:
            API response with download URL
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        url = f"{self.base_url}/{media_id}"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def download_media(self, media_url: str) -> bytes:
        """
        Download media from WhatsApp servers.

        Args:
            media_url: URL of the media file

        Returns:
            Media file content as bytes
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(media_url, headers=headers)
            response.raise_for_status()
            return response.content

    async def mark_message_as_read(self, message_id: str) -> dict[str, Any]:
        """
        Mark a message as read.

        Args:
            message_id: ID of the message to mark as read

        Returns:
            API response
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = self._get_headers()

        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def send_message(self, request: WhatsAppSendMessageRequest) -> WhatsAppSendMessageResponse:
        """
        Send a message based on the request type.

        Args:
            request: Message send request

        Returns:
            API response
        """
        if request.message_type == "text" and request.text:
            response = await self.send_text_message(
                to=request.to,
                text=request.text.body,
                preview_url=request.text.preview_url,
            )
        elif request.message_type == "template" and request.template:
            response = await self.send_template_message(
                to=request.to,
                template_name=request.template.name,
                components=request.template.components,
                language_code=request.template.language.get("code", "en_US"),
            )
        elif request.message_type in ["image", "document", "audio", "video"] and request.media:
            response = await self.send_media_message(
                to=request.to,
                media_type=request.media.media_type,
                media_id=request.media.media_id,
                url=request.media.url,
                caption=request.media.caption,
            )
        else:
            raise ValueError(f"Unsupported message type: {request.message_type}")

        return WhatsAppSendMessageResponse(**response)

    async def verify_phone_number(self) -> dict[str, Any]:
        """
        Verify the phone number is configured correctly.

        Returns:
            Phone number information
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        url = f"{self.base_url}/{self.phone_number_id}"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
