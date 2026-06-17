"""WhatsApp Business API webhook endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from app.core.config import settings
from app.schemas.whatsapp import (
    WhatsAppWebhookPayload,
    WhatsAppWebhookVerifyRequest,
)
from app.services.whatsapp_client import WhatsAppAPIClient
from app.services.whatsapp_parser import WhatsAppMessageParser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# Initialize services
parser = WhatsAppMessageParser()
client = WhatsAppAPIClient()


@router.get("/webhook")
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    challenge: str = Query(..., alias="hub.challenge"),
    verify_token: str = Query(..., alias="hub.verify_token"),
) -> Response:
    """
    Verify webhook with Facebook/Meta.

    This endpoint is called by Meta when setting up the webhook.
    It verifies that the webhook is owned by the application.
    """
    # Check if the mode is 'subscribe'
    if mode != "subscribe":
        logger.warning(f"Invalid hub.mode: {mode}")
        raise HTTPException(status_code=403, detail="Invalid hub.mode")

    # Check if the verify token matches
    if verify_token != settings.whatsapp_webhook_verify_token:
        logger.warning(f"Invalid verify token: {verify_token}")
        raise HTTPException(status_code=403, detail="Invalid verification token")

    # Return the challenge to confirm the webhook
    logger.info("Webhook verification successful")
    return Response(content=challenge, media_type="text/plain")


@router.post("/webhook")
async def receive_webhook(
    payload: WhatsAppWebhookPayload,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Receive incoming WhatsApp messages from webhook.

    This endpoint processes incoming messages from WhatsApp Business API.
    Messages are parsed and queued for processing.
    """
    if not settings.whatsapp_enabled:
        logger.warning("WhatsApp is not enabled, ignoring webhook")
        return {"status": "ignored", "reason": "WhatsApp not enabled"}

    # Process each entry in the webhook payload
    for entry in payload.entry:
        for change in entry.changes:
            if change.field == "messages":
                await _process_message_change(change.value, background_tasks)
            elif change.field == "messaging_postbacks":
                await _process_postback(change.value, background_tasks)
            elif change.field == "statuses":
                await _process_message_status(change.value)
            else:
                logger.debug(f"Unhandled field: {change.field}")

    return {"status": "received"}


async def _process_message_change(
    value: dict[str, Any], background_tasks: BackgroundTasks
) -> None:
    """Process a message change from webhook."""
    try:
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])
        metadata = value.get("metadata", {})

        for msg in messages:
            # Get phone number from message
            phone_number = msg.get("from")
            if not phone_number:
                logger.warning("Message without phone number, skipping")
                continue

            # Get contact info if available
            contact_info = {}
            for contact in contacts:
                if contact.get("wa_id") == phone_number:
                    contact_info = contact
                    break

            # Parse the message
            from app.schemas.whatsapp import WhatsAppMessage
            whatsapp_message = WhatsAppMessage(**msg)
            parsed_message = parser.parse_message(whatsapp_message, phone_number)

            logger.info(
                f"Received WhatsApp message from {phone_number}: "
                f"type={parsed_message.message_type}, "
                f"content={parsed_message.content[:50] if parsed_message.content else 'None'}"
            )

            # Queue the message for processing
            background_tasks.add_task(
                _queue_message_for_processing,
                parsed_message,
                contact_info,
                metadata,
            )

    except Exception as e:
        logger.exception(f"Error processing message change: {e}")


async def _process_postback(
    value: dict[str, Any], background_tasks: BackgroundTasks
) -> None:
    """Process a postback (button/list response) from webhook."""
    try:
        phone_number = value.get("from")
        postback = value.get("postback", {})
        payload = postback.get("data", "")

        logger.info(f"Received postback from {phone_number}: {payload}")

        # Process the postback (e.g., opt-in/opt-out, template selection)
        background_tasks.add_task(
            _process_postback_action,
            phone_number,
            payload,
        )

    except Exception as e:
        logger.exception(f"Error processing postback: {e}")


async def _process_message_status(value: dict[str, Any]) -> None:
    """Process message status updates (sent, delivered, read)."""
    try:
        status = value.get("status")
        message_id = value.get("id")
        recipient_id = value.get("recipient_id")

        logger.info(
            f"Message status update: message_id={message_id}, "
            f"status={status}, recipient={recipient_id}"
        )

        # Update message status in database if needed
        # This can be used for delivery tracking

    except Exception as e:
        logger.exception(f"Error processing message status: {e}")


async def _queue_message_for_processing(
    parsed_message: Any,
    contact_info: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    """
    Queue the parsed message for processing by the AI system.

    This integrates with the existing message queue system.
    """
    try:
        from app.services.message_queue import MessageQueueService

        queue = MessageQueueService()

        # Convert to internal message format
        internal_message = {
            "channel": "whatsapp",
            "phone_number": parsed_message.phone_number,
            "message_id": parsed_message.message_id,
            "message_type": parsed_message.message_type,
            "content": parsed_message.content,
            "attachments": [
                {
                    "type": att.type,
                    "media_id": att.media_id,
                    "mime_type": att.mime_type,
                    "file_size": att.file_size,
                    "caption": getattr(att, "caption", None),
                    "filename": getattr(att, "filename", None),
                }
                for att in parsed_message.attachments
            ],
            "timestamp": parsed_message.timestamp.isoformat(),
            "is_opt_out": parsed_message.is_opt_out,
            "is_opt_in": parsed_message.is_opt_in,
            "context_message_id": parsed_message.context_message_id,
            "contact_info": contact_info,
            "metadata": metadata,
        }

        # Add to message queue
        await queue.add_to_queue("whatsapp_queue", internal_message)

        logger.info(f"Queued message from {parsed_message.phone_number} for processing")

    except Exception as e:
        logger.exception(f"Error queuing message for processing: {e}")


async def _process_postback_action(phone_number: str, payload: str) -> None:
    """Process postback action (e.g., opt-in/opt-out)."""
    try:
        # Handle opt-in/opt-out postbacks
        if payload.startswith("opt_in_"):
            await _handle_opt_in(phone_number, payload)
        elif payload.startswith("opt_out_"):
            await _handle_opt_out(phone_number, payload)
        else:
            logger.info(f"Unhandled postback payload: {payload}")

    except Exception as e:
        logger.exception(f"Error processing postback action: {e}")


async def _handle_opt_in(phone_number: str, payload: str) -> None:
    """Handle opt-in action."""
    try:
        logger.info(f"Opt-in request from {phone_number}")

        # Update user opt-in status in database
        # Send confirmation message
        await client.send_text_message(
            to=phone_number,
            text="You have successfully opted in to receive messages from us.",
        )

    except Exception as e:
        logger.exception(f"Error handling opt-in: {e}")


async def _handle_opt_out(phone_number: str, payload: str) -> None:
    """Handle opt-out action."""
    try:
        logger.info(f"Opt-out request from {phone_number}")

        # Update user opt-out status in database
        # Send confirmation message
        await client.send_text_message(
            to=phone_number,
            text="You have been opted out. You will no longer receive messages from us.",
        )

    except Exception as e:
        logger.exception(f"Error handling opt-out: {e}")


@router.get("/health")
async def whatsapp_health() -> dict[str, Any]:
    """Check WhatsApp API health and configuration."""
    health_status = {
        "enabled": settings.whatsapp_enabled,
        "configured": bool(
            settings.whatsapp_phone_number_id
            and settings.whatsapp_access_token
            and settings.whatsapp_webhook_verify_token
        ),
    }

    if health_status["enabled"] and health_status["configured"]:
        try:
            # Verify phone number with Meta API
            phone_info = await client.verify_phone_number()
            health_status["phone_number"] = phone_info.get("display_phone_number")
            health_status["status"] = "healthy"
        except Exception as e:
            health_status["status"] = "error"
            health_status["error"] = str(e)
    else:
        health_status["status"] = "disabled"

    return health_status
