"""CRM webhook listener for real-time CRM updates."""

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any, Callable, Optional

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from .crm_models import CRMType, CRMWebhookEvent

logger = logging.getLogger(__name__)


class WebhookConfig(BaseModel):
    """Webhook configuration."""

    webhook_secret: str = Field(description="Webhook secret for signature verification")
    allowed_ips: list[str] = Field(default_factory=list, description="Allowed IP addresses")
    verify_signature: bool = Field(default=True, description="Whether to verify webhook signature")


class WebhookListener:
    """CRM webhook listener for real-time updates."""

    def __init__(self, config: WebhookConfig):
        """
        Initialize webhook listener.

        Args:
            config: Webhook configuration
        """
        self.config = config
        self.event_handlers: dict[str, list[Callable]] = {}
        self.event_queue: list[CRMWebhookEvent] = []

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """
        Register event handler for specific event type.

        Args:
            event_type: Event type (e.g., "contact.created", "account.updated")
            handler: Handler function
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []

        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered handler for event type: {event_type}")

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify webhook signature.

        Args:
            payload: Raw payload bytes
            signature: Signature from webhook header

        Returns:
            True if signature is valid
        """
        if not self.config.verify_signature:
            return True

        expected_signature = hmac.new(
            self.config.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        is_valid = hmac.compare_digest(expected_signature, signature)
        if not is_valid:
            logger.warning("Invalid webhook signature")

        return is_valid

    def verify_ip(self, request_ip: str) -> bool:
        """
        Verify request IP address.

        Args:
            request_ip: Request IP address

        Returns:
            True if IP is allowed
        """
        if not self.config.allowed_ips:
            return True

        is_allowed = request_ip in self.config.allowed_ips
        if not is_allowed:
            logger.warning(f"IP not allowed: {request_ip}")

        return is_allowed

    async def handle_webhook(self, request: Request) -> dict[str, Any]:
        """
        Handle incoming webhook request.

        Args:
            request: FastAPI request

        Returns:
            Response data

        Raises:
            HTTPException: If webhook validation fails
        """
        # Get request IP
        request_ip = request.client.host if request.client else "unknown"

        # Verify IP
        if not self.verify_ip(request_ip):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IP address not allowed",
            )

        # Get raw payload
        payload = await request.body()

        # Verify signature
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not self.verify_signature(payload, signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        # Parse payload
        try:
            data = json.loads(payload.decode())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload",
            )

        # Extract event information
        event_type = data.get("event_type", "unknown")
        crm_type = data.get("crm_type", "unknown")
        object_type = data.get("object_type", "unknown")
        object_id = data.get("object_id", "unknown")

        # Create webhook event
        event = CRMWebhookEvent(
            event_id=f"{crm_type}_{object_type}_{object_id}_{int(datetime.now(UTC).timestamp())}",
            event_type=event_type,
            crm_type=CRMType(crm_type) if crm_type in [e.value for e in CRMType] else CRMType.SALESFORCE,
            object_type=object_type,
            object_id=object_id,
            data=data,
        )

        # Add to queue
        self.event_queue.append(event)

        # Process event
        await self._process_event(event)

        logger.info(f"Webhook processed: {event_type} for {object_type} {object_id}")

        return {
            "status": "success",
            "event_id": event.event_id,
            "processed": True,
        }

    async def _process_event(self, event: CRMWebhookEvent) -> None:
        """
        Process webhook event.

        Args:
            event: Webhook event
        """
        event_type = event.event_type

        # Get handlers for this event type
        handlers = self.event_handlers.get(event_type, [])

        if not handlers:
            logger.warning(f"No handlers registered for event type: {event_type}")
            return

        # Execute all handlers
        for handler in handlers:
            try:
                await handler(event)
                event.processed = True
                event.processed_at = datetime.now(UTC)
            except Exception as e:
                logger.exception(f"Handler failed for event {event.event_id}: {e}")
                event.error_message = str(e)

    def get_event_queue(self) -> list[CRMWebhookEvent]:
        """
        Get event queue.

        Returns:
            List of events in queue
        """
        return self.event_queue.copy()

    def clear_event_queue(self) -> None:
        """Clear event queue."""
        self.event_queue.clear()
        logger.info("Event queue cleared")

    def get_unprocessed_events(self) -> list[CRMWebhookEvent]:
        """
        Get unprocessed events.

        Returns:
            List of unprocessed events
        """
        return [event for event in self.event_queue if not event.processed]

    async def retry_failed_events(self) -> int:
        """
        Retry processing failed events.

        Returns:
            Number of events retried
        """
        failed_events = [event for event in self.event_queue if not event.processed and event.error_message]

        retried_count = 0
        for event in failed_events:
            try:
                event.error_message = None
                await self._process_event(event)
                retried_count += 1
            except Exception as e:
                logger.exception(f"Retry failed for event {event.event_id}: {e}")
                event.error_message = str(e)

        logger.info(f"Retried {retried_count} failed events")
        return retried_count


async def create_webhook_endpoint(
    webhook_listener: WebhookListener,
    request: Request,
) -> dict[str, Any]:
    """
    FastAPI endpoint for webhooks.

    Args:
        webhook_listener: Webhook listener instance
        request: FastAPI request

    Returns:
        Response data
    """
    return await webhook_listener.handle_webhook(request)
