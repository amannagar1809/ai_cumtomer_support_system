"""Email webhook endpoints for receiving incoming emails."""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.schemas.email import EmailWebhookPayload, ParsedEmailMessage
from app.services.email_client import EmailClient
from app.services.email_parser import EmailParser
from app.services.email_rate_limit import EmailRateLimiter
from app.services.email_thread import EmailThreadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["email"])

# Initialize services
parser = EmailParser()
thread_service = EmailThreadService()
email_client = EmailClient()
rate_limiter = EmailRateLimiter()


@router.post("/webhook")
async def receive_email_webhook(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Receive incoming email from webhook (Postmark/SendGrid).

    This endpoint processes incoming emails from email providers.
    Emails are parsed, threaded, and queued for AI processing.
    """
    if not settings.email_enabled:
        logger.warning("Email is not enabled, ignoring webhook")
        return {"status": "ignored", "reason": "Email not enabled"}

    try:
        # Parse the email
        parsed_email = parser.parse_email(payload)

        logger.info(
            f"Received email from {parsed_email.from_email}: "
            f"subject={parsed_email.subject[:50]}, "
            f"is_reply={parsed_email.is_reply}"
        )

        # Check rate limit
        rate_info = await rate_limiter.check_rate_limit(parsed_email.from_email)
        if rate_info.remaining <= 0:
            logger.warning(
                f"Rate limit exceeded for {parsed_email.from_email}: "
                f"sent_today={rate_info.sent_today}, limit={rate_info.limit}"
            )
            # Send rate limit response email
            await _send_rate_limit_response(parsed_email.from_email)
            return {"status": "rate_limited", "reason": "Daily limit exceeded"}

        # Detect thread and link to conversation
        thread_info = await thread_service.detect_thread(parsed_email)
        parsed_email.conversation_id = thread_info.conversation_id

        logger.info(
            f"Email thread detected: thread_id={thread_info.thread_id}, "
            f"conversation_id={thread_info.conversation_id}"
        )

        # Queue the email for AI processing
        background_tasks.add_task(
            _queue_email_for_processing,
            parsed_email,
            thread_info,
        )

        return {"status": "received", "thread_id": thread_info.thread_id}

    except Exception as e:
        logger.exception(f"Error processing email webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process email")


async def _queue_email_for_processing(
    parsed_email: ParsedEmailMessage,
    thread_info: Any,
) -> None:
    """
    Queue the parsed email for processing by the AI system.

    This integrates with the existing message queue system.
    """
    try:
        from app.services.message_queue import MessageQueueService

        queue = MessageQueueService()

        # Convert to internal message format
        internal_message = {
            "channel": "email",
            "from_email": parsed_email.from_email,
            "from_name": parsed_email.from_name,
            "to_emails": parsed_email.to_emails,
            "subject": parsed_email.subject,
            "message_id": parsed_email.message_id,
            "message_type": "email",
            "content": parsed_email.extracted_body,
            "text_body": parsed_email.text_body,
            "html_body": parsed_email.html_body,
            "attachments": [
                {
                    "filename": att.filename,
                    "content_type": att.content_type,
                    "size": att.size,
                    "content_id": att.content_id,
                    "url": att.url,
                }
                for att in parsed_email.attachments
            ],
            "timestamp": parsed_email.received_at.isoformat(),
            "is_reply": parsed_email.is_reply,
            "in_reply_to": parsed_email.in_reply_to,
            "references": parsed_email.references,
            "thread_id": parsed_email.thread_id,
            "conversation_id": str(parsed_email.conversation_id) if parsed_email.conversation_id else None,
        }

        # Add to message queue
        await queue.add_to_queue("email_queue", internal_message)

        logger.info(f"Queued email from {parsed_email.from_email} for processing")

    except Exception as e:
        logger.exception(f"Error queuing email for processing: {e}")


async def _send_rate_limit_response(email: str) -> None:
    """Send rate limit response email to sender."""
    try:
        subject = "Daily Email Limit Reached"
        body = (
            "You have reached your daily limit of 50 emails to our support system. "
            "Please try again tomorrow or contact us through another channel for urgent matters."
        )

        await email_client.send_reply(
            to=email,
            subject=subject,
            body=body,
        )

        logger.info(f"Sent rate limit response to {email}")

    except Exception as e:
        logger.exception(f"Error sending rate limit response: {e}")


@router.post("/webhook/postmark")
async def receive_postmark_webhook(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Receive Postmark webhook specifically.

    Postmark sends webhooks in a specific format.
    """
    return await receive_email_webhook(payload, background_tasks)


@router.post("/webhook/sendgrid")
async def receive_sendgrid_webhook(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Receive SendGrid webhook specifically.

    SendGrid sends webhooks in a specific format.
    """
    # SendGrid webhooks come as an array of events
    events = payload if isinstance(payload, list) else [payload]

    for event in events:
        # Process only inbound events
        if event.get("event") == "inbound":
            # Convert SendGrid format to standard format
            standard_payload = {
                "From": event.get("from", ""),
                "To": event.get("to", ""),
                "Subject": event.get("subject", ""),
                "MessageID": event.get("message_id", ""),
                "TextBody": event.get("text", ""),
                "HtmlBody": event.get("html", ""),
                "Attachments": event.get("attachments", []),
                "Headers": event.get("headers", {}),
                "InReplyTo": event.get("in_reply_to"),
                "References": event.get("references", []),
            }
            await receive_email_webhook(standard_payload, background_tasks)

    return {"status": "received"}


@router.get("/health")
async def email_health() -> dict[str, Any]:
    """Check email service health and configuration."""
    health_status = {
        "enabled": settings.email_enabled,
        "configured": bool(
            settings.email_postmark_api_key or settings.email_sendgrid_api_key
        ),
        "provider": settings.email_provider,
        "rate_limit_per_day": settings.email_rate_limit_per_day,
    }

    if health_status["enabled"] and health_status["configured"]:
        health_status["status"] = "healthy"
    else:
        health_status["status"] = "disabled"

    return health_status


@router.get("/rate-limit/{email}")
async def check_rate_limit(email: str) -> dict[str, Any]:
    """Check rate limit status for a specific email address."""
    rate_info = await rate_limiter.check_rate_limit(email)
    return {
        "email": rate_info.email,
        "sent_today": rate_info.sent_today,
        "limit": rate_info.limit,
        "remaining": rate_info.remaining,
        "reset_at": rate_info.reset_at.isoformat(),
    }
