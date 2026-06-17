"""Email parser service for parsing incoming emails and extracting context."""

import logging
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from app.schemas.email import (
    EmailAttachment,
    EmailQuotedReply,
    EmailSignatureDetection,
    EmailThreadInfo,
    ParsedEmailMessage,
)

logger = logging.getLogger(__name__)


class EmailParser:
    """Parse incoming emails and extract relevant information."""

    def __init__(self):
        # Common signature patterns
        self.signature_patterns = [
            r"--\s*\n",  # Standard signature delimiter
            r"---\s*\n",  # Alternative signature delimiter
            r"Best regards,?\s*\n",
            r"Regards,?\s*\n",
            r"Sincerely,?\s*\n",
            r"Thanks,?\s*\n",
            r"Thank you,?\s*\n",
            r"Cheers,?\s*\n",
            r"Sent from my (iPhone|iPad|Android|BlackBerry|Windows Phone)",
            r"Get (Outlook|Gmail|Yahoo Mail) for",
            r"Disclaimer:",
            r"Confidentiality Notice:",
            r"This message is intended only for",
        ]

        # Common quoted reply patterns
        self.reply_patterns = [
            r"On .+ wrote:",  # "On [date] [person] wrote:"
            r"From: .+\nSent: .+\nTo: .+\nSubject:",  # Outlook style
            r"-----Original Message-----",  # Standard reply header
            r">",  # Email quote character
            r"Quoted text:",
        ]

    def parse_email(self, webhook_payload: dict[str, Any]) -> ParsedEmailMessage:
        """
        Parse incoming email webhook payload.

        Args:
            webhook_payload: Raw webhook payload from email provider

        Returns:
            Parsed email message
        """
        # Extract basic fields
        from_address = self._extract_email_address(webhook_payload.get("From", ""))
        from_name = self._extract_name(webhook_payload.get("From", ""))
        to_addresses = self._extract_email_list(webhook_payload.get("To", []))
        subject = webhook_payload.get("Subject", "")
        message_id = webhook_payload.get("MessageID", "")
        text_body = webhook_payload.get("TextBody")
        html_body = webhook_payload.get("HtmlBody")
        attachments = self._parse_attachments(webhook_payload.get("Attachments", []))
        in_reply_to = webhook_payload.get("InReplyTo")
        references = webhook_payload.get("References", [])
        received_at = webhook_payload.get("ReceivedAt", datetime.utcnow())

        # Determine if this is a reply
        is_reply = bool(in_reply_to or references)

        # Extract thread ID
        thread_id = self._extract_thread_id(message_id, in_reply_to, references)

        # Extract clean body (remove signatures and quoted replies)
        clean_body = self._extract_clean_body(text_body or html_body or "")

        return ParsedEmailMessage(
            message_id=message_id,
            from_email=from_address,
            from_name=from_name,
            to_emails=to_addresses,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            attachments=attachments,
            received_at=received_at,
            in_reply_to=in_reply_to,
            references=references,
            thread_id=thread_id,
            extracted_body=clean_body,
            is_reply=is_reply,
            conversation_id=None,  # Will be set by thread detection service
        )

    def _extract_email_address(self, email_string: str) -> str:
        """Extract email address from email string (e.g., "John Doe <john@example.com>")."""
        if not email_string:
            return ""

        # Try to extract email from angle brackets
        match = re.search(r"<([^>]+)>", email_string)
        if match:
            return match.group(1).strip()

        # If no angle brackets, return the string as-is
        return email_string.strip()

    def _extract_name(self, email_string: str) -> str | None:
        """Extract name from email string."""
        if not email_string:
            return None

        # Try to extract name before angle brackets
        match = re.search(r"([^<]+)<", email_string)
        if match:
            name = match.group(1).strip()
            # Remove quotes if present
            name = name.strip('"\'')
            return name if name else None

        return None

    def _extract_email_list(self, email_list: Any) -> list[str]:
        """Extract list of email addresses from various formats."""
        if not email_list:
            return []

        if isinstance(email_list, str):
            return [self._extract_email_address(email_list)]

        if isinstance(email_list, list):
            return [self._extract_email_address(str(e)) for e in email_list]

        return []

    def _parse_attachments(self, attachments: Any) -> list[EmailAttachment]:
        """Parse attachment list."""
        if not attachments:
            return []

        parsed_attachments = []
        for att in attachments:
            try:
                parsed_attachments.append(
                    EmailAttachment(
                        filename=att.get("Name", ""),
                        content_type=att.get("ContentType", ""),
                        size=att.get("ContentLength", 0),
                        content_id=att.get("ContentID"),
                        url=att.get("URL"),
                        data=att.get("Content"),  # Base64 encoded
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to parse attachment: {e}")

        return parsed_attachments

    def _extract_thread_id(
        self, message_id: str, in_reply_to: str | None, references: list[str]
    ) -> str:
        """Extract thread ID from message headers."""
        # Try to get thread ID from references
        if references:
            return references[0]

        # Use In-Reply-To as thread ID
        if in_reply_to:
            return in_reply_to

        # Use message ID as thread ID for new threads
        return message_id

    def _extract_clean_body(self, body: str) -> str:
        """Extract clean body by removing signatures and quoted replies."""
        if not body:
            return ""

        # Remove HTML tags if present
        clean_body = self._strip_html(body)

        # Remove quoted replies
        clean_body = self._remove_quoted_replies(clean_body)

        # Remove signatures
        clean_body = self._remove_signatures(clean_body)

        # Clean up whitespace
        clean_body = re.sub(r"\n\s*\n\s*\n", "\n\n", clean_body)
        clean_body = clean_body.strip()

        return clean_body

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags and convert to plain text."""
        if not html:
            return ""

        # Simple HTML tag removal (for production, use a proper library like bleach)
        clean = re.sub(r"<[^>]+>", "", html)
        clean = re.sub(r"&nbsp;", " ", clean)
        clean = re.sub(r"&lt;", "<", clean)
        clean = re.sub(r"&gt;", ">", clean)
        clean = re.sub(r"&amp;", "&", clean)
        clean = re.sub(r"\n\s*\n", "\n\n", clean)
        return clean.strip()

    def _remove_quoted_replies(self, body: str) -> str:
        """Remove quoted reply text from email body."""
        lines = body.split("\n")
        clean_lines = []
        in_quote = False

        for line in lines:
            # Check if line starts a quoted section
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in self.reply_patterns):
                in_quote = True
                continue

            # Check if line is a quote line (starts with >)
            if line.strip().startswith(">"):
                in_quote = True
                continue

            # Add line if not in quote
            if not in_quote:
                clean_lines.append(line)
            # Reset quote flag if we hit an empty line after quotes
            elif in_quote and not line.strip():
                in_quote = False

        return "\n".join(clean_lines)

    def _remove_signatures(self, body: str) -> str:
        """Remove email signatures from body."""
        lines = body.split("\n")
        clean_lines = []

        for line in lines:
            # Check if line starts a signature
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in self.signature_patterns):
                break

            clean_lines.append(line)

        return "\n".join(clean_lines)

    def detect_signature(self, body: str) -> EmailSignatureDetection:
        """
        Detect email signature in body.

        Args:
            body: Email body text

        Returns:
            Signature detection information
        """
        if not body:
            return EmailSignatureDetection(
                has_signature=False, signature_start=None, signature_text=None, confidence=0.0
            )

        lines = body.split("\n")
        for i, line in enumerate(lines):
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in self.signature_patterns):
                signature_text = "\n".join(lines[i:])
                return EmailSignatureDetection(
                    has_signature=True,
                    signature_start=i,
                    signature_text=signature_text,
                    confidence=0.8,  # Basic confidence score
                )

        return EmailSignatureDetection(
            has_signature=False, signature_start=None, signature_text=None, confidence=0.0
        )

    def extract_quoted_reply(self, body: str) -> EmailQuotedReply:
        """
        Extract quoted reply text from body.

        Args:
            body: Email body text

        Returns:
            Quoted reply information
        """
        if not body:
            return EmailQuotedReply(
                has_quoted_text=False, quoted_text="", quoted_start=0, clean_body=body
            )

        lines = body.split("\n")
        quoted_lines = []
        clean_lines = []
        in_quote = False
        quote_start = 0

        for i, line in enumerate(lines):
            # Check if line starts a quoted section
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in self.reply_patterns):
                in_quote = True
                quote_start = i
                continue

            # Check if line is a quote line
            if line.strip().startswith(">"):
                if not in_quote:
                    quote_start = i
                    in_quote = True
                quoted_lines.append(line)
                continue

            # Add to clean lines if not in quote
            if not in_quote:
                clean_lines.append(line)
            # Reset quote flag
            elif in_quote and not line.strip():
                in_quote = False

        quoted_text = "\n".join(quoted_lines)
        clean_body = "\n".join(clean_lines)

        return EmailQuotedReply(
            has_quoted_text=bool(quoted_text),
            quoted_text=quoted_text,
            quoted_start=quote_start,
            clean_body=clean_body,
        )
