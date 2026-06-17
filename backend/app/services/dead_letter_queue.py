"""Dead-letter queue for failed channel messages."""

import json
import logging
from datetime import datetime
from typing import Any

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """Dead-letter queue for storing failed messages."""

    def __init__(self):
        self.redis_prefix = "dead_letter_queue"
        self.max_queue_size = 1000

    async def add_message(
        self, channel: str, raw_message: dict[str, Any], error: str
    ) -> str:
        """
        Add a failed message to the dead-letter queue.

        Args:
            channel: Channel name
            raw_message: Raw message that failed
            error: Error message

        Returns:
            Queue entry ID
        """
        redis = await get_redis_client()

        try:
            entry = {
                "channel": channel,
                "raw_message": raw_message,
                "error": error,
                "timestamp": datetime.utcnow().isoformat(),
                "retry_count": 0,
            }

            key = f"{self.redis_prefix}:{channel}"
            entry_id = await redis.lpush(key, json.dumps(entry))

            # Trim queue to max size
            await redis.ltrim(key, 0, self.max_queue_size - 1)

            logger.warning(
                f"Added message to dead-letter queue for channel {channel}: {error}"
            )
            return str(entry_id)

        except Exception as e:
            logger.exception(f"Error adding message to dead-letter queue: {e}")
            raise

    async def get_messages(self, channel: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get failed messages from the dead-letter queue for a channel.

        Args:
            channel: Channel name
            limit: Maximum number of messages to retrieve

        Returns:
            List of failed messages
        """
        redis = await get_redis_client()

        try:
            key = f"{self.redis_prefix}:{channel}"
            messages_json = await redis.lrange(key, 0, limit - 1)

            messages = []
            for msg_json in messages_json:
                try:
                    msg = json.loads(msg_json)
                    messages.append(msg)
                except Exception as e:
                    logger.warning(f"Failed to parse dead-letter queue entry: {e}")

            return messages

        except Exception as e:
            logger.exception(f"Error getting messages from dead-letter queue: {e}")
            return []

    async def retry_message(self, channel: str, entry: dict[str, Any]) -> bool:
        """
        Retry a failed message from the dead-letter queue.

        Args:
            channel: Channel name
            entry: Queue entry to retry

        Returns:
            True if retry was successful
        """
        try:
            from app.services.channel_router import ChannelRouter

            router = ChannelRouter()

            # Increment retry count
            entry["retry_count"] += 1
            entry["last_retry"] = datetime.utcnow().isoformat()

            # Try to handle the message again
            result = await router.handle_message(channel, entry["raw_message"])

            if result.get("success"):
                # Remove from dead-letter queue
                await self.remove_message(channel, entry)
                logger.info(f"Successfully retried message from dead-letter queue for {channel}")
                return True
            else:
                # Update entry with new error
                entry["error"] = result.get("error", "Unknown error")
                await self.update_entry(channel, entry)
                return False

        except Exception as e:
            logger.exception(f"Error retrying message from dead-letter queue: {e}")
            entry["error"] = str(e)
            await self.update_entry(channel, entry)
            return False

    async def remove_message(self, channel: str, entry: dict[str, Any]) -> bool:
        """
        Remove a message from the dead-letter queue.

        Args:
            channel: Channel name
            entry: Queue entry to remove

        Returns:
            True if removed successfully
        """
        redis = await get_redis_client()

        try:
            key = f"{self.redis_prefix}:{channel}"
            entry_json = json.dumps(entry)

            # Remove the specific entry
            await redis.lrem(key, 1, entry_json)

            logger.info(f"Removed message from dead-letter queue for {channel}")
            return True

        except Exception as e:
            logger.exception(f"Error removing message from dead-letter queue: {e}")
            return False

    async def update_entry(self, channel: str, entry: dict[str, Any]) -> bool:
        """
        Update an entry in the dead-letter queue.

        Args:
            channel: Channel name
            entry: Updated queue entry

        Returns:
            True if updated successfully
        """
        redis = await get_redis_client()

        try:
            key = f"{self.redis_prefix}:{channel}"
            old_entry_json = json.dumps(
                {k: v for k, v in entry.items() if k not in ["retry_count", "last_retry"]}
            )

            # Remove old entry and add updated one
            await redis.lrem(key, 1, old_entry_json)
            await redis.lpush(key, json.dumps(entry))

            return True

        except Exception as e:
            logger.exception(f"Error updating dead-letter queue entry: {e}")
            return False

    async def clear_queue(self, channel: str) -> int:
        """
        Clear all messages from the dead-letter queue for a channel.

        Args:
            channel: Channel name

        Returns:
            Number of messages cleared
        """
        redis = await get_redis_client()

        try:
            key = f"{self.redis_prefix}:{channel}"
            count = await redis.llen(key)
            await redis.delete(key)

            logger.info(f"Cleared {count} messages from dead-letter queue for {channel}")
            return count

        except Exception as e:
            logger.exception(f"Error clearing dead-letter queue: {e}")
            return 0

    async def get_queue_stats(self, channel: str | None = None) -> dict[str, Any]:
        """
        Get statistics for the dead-letter queue.

        Args:
            channel: Channel name (optional, if None returns stats for all channels)

        Returns:
            Queue statistics
        """
        redis = await get_redis_client()

        try:
            if channel:
                key = f"{self.redis_prefix}:{channel}"
                count = await redis.llen(key)
                return {
                    "channel": channel,
                    "queue_size": count,
                }
            else:
                stats = {}
                for ch in ["whatsapp", "email", "telegram", "mobile"]:
                    key = f"{self.redis_prefix}:{ch}"
                    count = await redis.llen(key)
                    stats[ch] = count
                return stats

        except Exception as e:
            logger.exception(f"Error getting dead-letter queue stats: {e}")
            return {}

    async def purge_old_entries(self, channel: str, max_age_hours: int = 24) -> int:
        """
        Purge old entries from the dead-letter queue.

        Args:
            channel: Channel name
            max_age_hours: Maximum age in hours

        Returns:
            Number of entries purged
        """
        redis = await get_redis_client()

        try:
            key = f"{self.redis_prefix}:{channel}"
            messages_json = await redis.lrange(key, 0, -1)

            cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)
            purged_count = 0

            for msg_json in messages_json:
                try:
                    msg = json.loads(msg_json)
                    timestamp = datetime.fromisoformat(msg["timestamp"])
                    if timestamp.timestamp() < cutoff_time:
                        await redis.lrem(key, 1, msg_json)
                        purged_count += 1
                except Exception as e:
                    logger.warning(f"Failed to parse dead-letter queue entry: {e}")

            logger.info(
                f"Purged {purged_count} old entries from dead-letter queue for {channel}"
            )
            return purged_count

        except Exception as e:
            logger.exception(f"Error purging old entries from dead-letter queue: {e}")
            return 0
