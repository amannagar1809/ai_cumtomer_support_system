"""Abstract ChannelConnector base class for unified multi-channel support."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class NormalizedMessage(BaseModel):
    """Normalized message format for all channels."""

    conversation_id: UUID | None = None
    user_id: UUID | None = None
    channel: str
    channel_message_id: str
    sender_type: str  # "customer" or "agent"
    content: str | None = None
    attachments: list[dict[str, Any]] = []
    timestamp: datetime
    language: str | None = None
    metadata: dict[str, Any] = {}  # Channel-specific metadata


class ChannelConnector(ABC):
    """Abstract base class for channel connectors."""

    def __init__(self, channel_name: str):
        self.channel_name = channel_name
        self.last_successful_message: datetime | None = None
        self.failure_count: int = 0
        self.is_healthy: bool = True

    @abstractmethod
    async def normalize_message(self, raw_message: dict[str, Any]) -> NormalizedMessage:
        """
        Normalize a raw channel message to the standard format.

        Args:
            raw_message: Raw message from the channel

        Returns:
            Normalized message
        """
        pass

    @abstractmethod
    async def get_user_identifier(self, raw_message: dict[str, Any]) -> str:
        """
        Extract user identifier from raw message.

        Args:
            raw_message: Raw message from the channel

        Returns:
            User identifier (phone, email, user_id, etc.)
        """
        pass

    @abstractmethod
    async def send_response(
        self, conversation_id: UUID, message: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        """
        Send a response message through the channel.

        Args:
            conversation_id: Conversation ID
            message: Message content
            metadata: Optional channel-specific metadata

        Returns:
            True if sent successfully
        """
        pass

    async def process_message(self, raw_message: dict[str, Any]) -> NormalizedMessage:
        """
        Process a raw message through the connector.

        Args:
            raw_message: Raw message from the channel

        Returns:
            Normalized message

        Raises:
            Exception: If processing fails
        """
        try:
            normalized = await self.normalize_message(raw_message)
            self.last_successful_message = datetime.utcnow()
            self.failure_count = 0
            self.is_healthy = True
            logger.info(f"Successfully processed message from {self.channel_name}")
            return normalized
        except Exception as e:
            self.failure_count += 1
            self.is_healthy = False
            logger.exception(f"Failed to process message from {self.channel_name}: {e}")
            raise

    def get_health_status(self) -> dict[str, Any]:
        """
        Get the health status of the channel connector.

        Returns:
            Health status dictionary
        """
        return {
            "channel": self.channel_name,
            "is_healthy": self.is_healthy,
            "last_successful_message": self.last_successful_message.isoformat()
            if self.last_successful_message
            else None,
            "failure_count": self.failure_count,
        }

    def reset_health_status(self) -> None:
        """Reset the health status of the channel connector."""
        self.last_successful_message = None
        self.failure_count = 0
        self.is_healthy = True
