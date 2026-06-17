"""Email API client for sending responses via Postmark, SendGrid, or custom SMTP."""

import logging
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.email import (
    EmailAttachment,
    SendEmailRequest,
    SendEmailResponse,
)

logger = logging.getLogger(__name__)


class EmailClient:
    """Client for sending emails via various providers."""

    def __init__(self):
        self.provider = settings.email_provider
        self.from_address = settings.email_from_address
        self.from_name = settings.email_from_name
        self.reply_to = settings.email_reply_to
        self.timeout = 30.0

    async def send_email(self, request: SendEmailRequest) -> SendEmailResponse:
        """
        Send email based on configured provider.

        Args:
            request: Email send request

        Returns:
            Send email response
        """
        if not settings.email_enabled:
            logger.warning("Email is not enabled")
            raise ValueError("Email is not enabled")

        if self.provider == "postmark":
            return await self._send_via_postmark(request)
        elif self.provider == "sendgrid":
            return await self._send_via_sendgrid(request)
        else:
            raise ValueError(f"Unsupported email provider: {self.provider}")

    async def _send_via_postmark(self, request: SendEmailRequest) -> SendEmailResponse:
        """Send email via Postmark API."""
        if not settings.email_postmark_api_key:
            raise ValueError("Postmark API key not configured")

        url = "https://api.postmarkapp.com/email"
        headers = {
            "X-Postmark-Server-Token": settings.email_postmark_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Build Postmark payload
        payload = {
            "From": request.from_address or self.from_address,
            "To": request.to if isinstance(request.to, str) else ",".join(request.to),
            "Subject": request.subject,
            "TextBody": request.text_body,
            "HtmlBody": request.html_body,
            "ReplyTo": request.reply_to or self.reply_to,
        }

        # Add CC and BCC
        if request.cc:
            payload["Cc"] = ",".join(request.cc)
        if request.bcc:
            payload["Bcc"] = ",".join(request.bcc)

        # Add attachments
        if request.attachments:
            payload["Attachments"] = [
                self._convert_attachment_for_postmark(att) for att in request.attachments
            ]

        # Add reply headers for threading
        if request.in_reply_to:
            payload["Headers"] = [
                {"Name": "In-Reply-To", "Value": request.in_reply_to}
            ]
        if request.references:
            if "Headers" not in payload:
                payload["Headers"] = []
            payload["Headers"].append(
                {"Name": "References", "Value": " ".join(request.references)}
            )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            return SendEmailResponse(
                message_id=result.get("MessageID", ""),
                to=str(request.to),
                subject=request.subject,
                sent_at=datetime.utcnow(),
                provider="postmark",
            )

    async def _send_via_sendgrid(self, request: SendEmailRequest) -> SendEmailResponse:
        """Send email via SendGrid API."""
        if not settings.email_sendgrid_api_key:
            raise ValueError("SendGrid API key not configured")

        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {settings.email_sendgrid_api_key}",
            "Content-Type": "application/json",
        }

        # Build SendGrid payload
        from_email = {
            "email": request.from_address or self.from_address,
            "name": request.from_name or self.from_name,
        }

        personalizations = [
            {
                "to": [{"email": request.to}] if isinstance(request.to, str) else [
                    {"email": addr} for addr in request.to
                ],
                "subject": request.subject,
            }
        ]

        # Add CC and BCC
        if request.cc:
            personalizations[0]["cc"] = [{"email": addr} for addr in request.cc]
        if request.bcc:
            personalizations[0]["bcc"] = [{"email": addr} for addr in request.bcc]

        # Add reply headers
        headers_dict = {}
        if request.in_reply_to:
            headers_dict["In-Reply-To"] = request.in_reply_to
        if request.references:
            headers_dict["References"] = " ".join(request.references)
        if headers_dict:
            personalizations[0]["headers"] = headers_dict

        content = []
        if request.text_body:
            content.append({"type": "text/plain", "value": request.text_body})
        if request.html_body:
            content.append({"type": "text/html", "value": request.html_body})

        payload = {
            "personalizations": personalizations,
            "from": from_email,
            "reply_to": {"email": request.reply_to or self.reply_to},
            "content": content,
        }

        # Add attachments
        if request.attachments:
            payload["attachments"] = [
                self._convert_attachment_for_sendgrid(att) for att in request.attachments
            ]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            # SendGrid doesn't return message ID in response body
            # It's in the X-Message-ID header
            message_id = response.headers.get("X-Message-ID", "")

            return SendEmailResponse(
                message_id=message_id,
                to=str(request.to),
                subject=request.subject,
                sent_at=datetime.utcnow(),
                provider="sendgrid",
            )

    def _convert_attachment_for_postmark(self, attachment: EmailAttachment) -> dict[str, Any]:
        """Convert attachment to Postmark format."""
        return {
            "Name": attachment.filename,
            "ContentType": attachment.content_type,
            "Content": attachment.data or "",  # Base64 encoded
        }

    def _convert_attachment_for_sendgrid(self, attachment: EmailAttachment) -> dict[str, Any]:
        """Convert attachment to SendGrid format."""
        return {
            "content": attachment.data or "",  # Base64 encoded
            "type": attachment.content_type,
            "filename": attachment.filename,
            "disposition": "attachment",
        }

    async def send_reply(
        self,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
        html_body: str | None = None,
    ) -> SendEmailResponse:
        """
        Send a reply email with proper threading headers.

        Args:
            to: Recipient email
            subject: Subject line
            body: Email body (text)
            in_reply_to: Message ID being replied to
            references: Thread references
            html_body: HTML body (optional)

        Returns:
            Send email response
        """
        request = SendEmailRequest(
            to=to,
            subject=subject,
            text_body=body,
            html_body=html_body,
            in_reply_to=in_reply_to,
            references=references or [],
        )

        return await self.send_email(request)

    async def send_template_email(
        self,
        to: str,
        template_id: str,
        template_data: dict[str, Any],
        subject: str | None = None,
    ) -> SendEmailResponse:
        """
        Send email using a template (provider-specific).

        Args:
            to: Recipient email
            template_id: Template ID
            template_data: Data for template variables
            subject: Optional subject override

        Returns:
            Send email response
        """
        if self.provider == "postmark":
            return await self._send_postmark_template(to, template_id, template_data, subject)
        elif self.provider == "sendgrid":
            return await self._send_sendgrid_template(to, template_id, template_data, subject)
        else:
            raise ValueError(f"Templates not supported for provider: {self.provider}")

    async def _send_postmark_template(
        self,
        to: str,
        template_id: str,
        template_data: dict[str, Any],
        subject: str | None = None,
    ) -> SendEmailResponse:
        """Send email via Postmark template."""
        if not settings.email_postmark_api_key:
            raise ValueError("Postmark API key not configured")

        url = "https://api.postmarkapp.com/email/withTemplate"
        headers = {
            "X-Postmark-Server-Token": settings.email_postmark_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {
            "From": self.from_address,
            "To": to,
            "TemplateId": template_id,
            "TemplateModel": template_data,
        }

        if subject:
            payload["Subject"] = subject

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            return SendEmailResponse(
                message_id=result.get("MessageID", ""),
                to=to,
                subject=subject or "",
                sent_at=datetime.utcnow(),
                provider="postmark",
            )

    async def _send_sendgrid_template(
        self,
        to: str,
        template_id: str,
        template_data: dict[str, Any],
        subject: str | None = None,
    ) -> SendEmailResponse:
        """Send email via SendGrid template."""
        if not settings.email_sendgrid_api_key:
            raise ValueError("SendGrid API key not configured")

        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {settings.email_sendgrid_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "personalizations": [
                {
                    "to": [{"email": to}],
                    "dynamic_template_data": template_data,
                }
            ],
            "from": {"email": self.from_address, "name": self.from_name},
            "template_id": template_id,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            message_id = response.headers.get("X-Message-ID", "")

            return SendEmailResponse(
                message_id=message_id,
                to=to,
                subject=subject or "",
                sent_at=datetime.utcnow(),
                provider="sendgrid",
            )
