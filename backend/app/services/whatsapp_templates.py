"""WhatsApp template message handling and approval process."""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class WhatsAppTemplateService:
    """Service for managing WhatsApp message templates."""

    def __init__(self):
        self.base_url = f"https://graph.facebook.com/{settings.whatsapp_api_version}"
        self.business_account_id = settings.whatsapp_business_account_id
        self.access_token = settings.whatsapp_access_token
        self.timeout = 30.0

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def create_template(
        self,
        name: str,
        category: str,
        language: str,
        components: list[dict[str, Any]],
        allow_category_change: bool = False,
    ) -> dict[str, Any]:
        """
        Create a new message template.

        Args:
            name: Template name (unique, lowercase, alphanumeric, underscores)
            category: Template category (MARKETING, UTILITY, AUTHENTICATION)
            language: Language code (e.g., en_US)
            components: Template components (header, body, footer, buttons)
            allow_category_change: Allow Meta to change category if needed

        Returns:
            API response with template ID
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        if not self.business_account_id:
            raise ValueError("WhatsApp business account ID not configured")

        url = f"{self.base_url}/{self.business_account_id}/message_templates"
        headers = self._get_headers()

        payload = {
            "name": name,
            "category": category,
            "language": language,
            "components": components,
            "allow_category_change": allow_category_change,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Created template: {name} with ID: {result.get('id')}")
            return result

    async def list_templates(
        self, limit: int = 100, status: str | None = None
    ) -> dict[str, Any]:
        """
        List all message templates for the business account.

        Args:
            limit: Number of templates to return
            status: Filter by status (APPROVED, PENDING, REJECTED, DISABLED)

        Returns:
            API response with template list
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        if not self.business_account_id:
            raise ValueError("WhatsApp business account ID not configured")

        url = f"{self.base_url}/{self.business_account_id}/message_templates"
        headers = self._get_headers()

        params = {"limit": limit}
        if status:
            params["status"] = status

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()

    async def get_template(self, template_id: str) -> dict[str, Any]:
        """
        Get details of a specific template.

        Args:
            template_id: Template ID

        Returns:
            Template details
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        url = f"{self.base_url}/{template_id}"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def delete_template(self, template_id: str) -> dict[str, Any]:
        """
        Delete a message template.

        Args:
            template_id: Template ID

        Returns:
            API response
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        url = f"{self.base_url}/{template_id}"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(url, headers=headers)
            response.raise_for_status()
            logger.info(f"Deleted template: {template_id}")
            return response.json()

    async def update_template(
        self, template_id: str, components: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Update an existing template.

        Args:
            template_id: Template ID
            components: Updated template components

        Returns:
            API response
        """
        if not settings.whatsapp_enabled:
            logger.warning("WhatsApp is not enabled")
            raise ValueError("WhatsApp is not enabled")

        url = f"{self.base_url}/{template_id}"
        headers = self._get_headers()

        payload = {"components": components}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"Updated template: {template_id}")
            return response.json()

    def build_text_component(
        self, text: str, variables: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Build a text component (header or body).

        Args:
            text: Template text with {{1}}, {{2}} for variables
            variables: List of variable names for documentation

        Returns:
            Component dictionary
        """
        component = {
            "type": "BODY" if not variables or "{{1}}" not in text else "BODY",
            "text": text,
        }

        if variables:
            component["example"] = {
                "body_text_content": [
                    [f"{{{{{i + 1}}}}}" for i in range(len(variables))]
                ]
            }

        return component

    def build_header_component(
        self, header_type: str, text: str | None = None, example: str | None = None
    ) -> dict[str, Any]:
        """
        Build a header component.

        Args:
            header_type: Type (TEXT, IMAGE, DOCUMENT, VIDEO)
            text: Header text (for TEXT type)
            example: Example header value

        Returns:
            Component dictionary
        """
        component = {"type": "HEADER", "format": header_type}

        if header_type == "TEXT" and text:
            component["text"] = text
            if example:
                component["example"] = {"header_text": [example]}

        return component

    def build_button_component(
        self, buttons: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Build a button component.

        Args:
            buttons: List of button configurations

        Returns:
            Component dictionary
        """
        return {
            "type": "BUTTONS",
            "buttons": buttons,
        }

    def build_quick_reply_button(
        self, payload: str, text: str
    ) -> dict[str, Any]:
        """
        Build a quick reply button.

        Args:
            payload: Data to send when button is clicked
            text: Button text

        Returns:
            Button configuration
        """
        return {
            "type": "QUICK_REPLY",
            "text": text,
            "payload": payload,
        }

    def build_call_button(
        self, text: str, phone_number: str
    ) -> dict[str, Any]:
        """
        Build a call button.

        Args:
            text: Button text
            phone_number: Phone number to call

        Returns:
            Button configuration
        """
        return {
            "type": "PHONE_NUMBER",
            "text": text,
            "phone_number": phone_number,
        }

    def build_url_button(
        self, text: str, url: str, variables: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Build a URL button.

        Args:
            text: Button text
            url: URL with {{1}} for variables
            variables: List of variable names

        Returns:
            Button configuration
        """
        button = {
            "type": "URL",
            "text": text,
            "url": url,
        }

        if variables:
            button["example"] = [f"{{{{{i + 1}}}}}" for i in range(len(variables))]

        return button

    def build_footer_component(self, text: str) -> dict[str, Any]:
        """
        Build a footer component.

        Args:
            text: Footer text

        Returns:
            Component dictionary
        """
        return {
            "type": "FOOTER",
            "text": text,
        }

    async def check_template_status(self, template_name: str) -> dict[str, Any]:
        """
        Check the approval status of a template.

        Args:
            template_name: Template name

        Returns:
            Template status information
        """
        try:
            templates = await self.list_templates()
            for template in templates.get("data", []):
                if template.get("name") == template_name:
                    return {
                        "name": template.get("name"),
                        "status": template.get("status"),
                        "category": template.get("category"),
                        "id": template.get("id"),
                    }
            return {"error": "Template not found"}
        except Exception as e:
            logger.exception(f"Error checking template status: {e}")
            return {"error": str(e)}
