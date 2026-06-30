"""Redis client for token storage and caching."""

import logging
from typing import Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client for token storage."""

    def __init__(self):
        """Initialize Redis client."""
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    def store_refresh_token(
        self,
        user_id: str,
        refresh_token: str,
        expires_in_seconds: int = 604800,  # 7 days
    ) -> bool:
        """
        Store refresh token in Redis with user binding.

        Args:
            user_id: User ID
            refresh_token: Refresh token
            expires_in_seconds: Expiration time in seconds (default: 7 days)

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            logger.error("Redis client not available")
            return False

        try:
            key = f"refresh_token:{user_id}"
            self.redis_client.setex(key, expires_in_seconds, refresh_token)
            logger.info(f"Refresh token stored for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to store refresh token: {e}")
            return False

    def get_refresh_token(self, user_id: str) -> Optional[str]:
        """
        Get refresh token for a user.

        Args:
            user_id: User ID

        Returns:
            Refresh token or None if not found
        """
        if not self.redis_client:
            logger.error("Redis client not available")
            return None

        try:
            key = f"refresh_token:{user_id}"
            token = self.redis_client.get(key)
            return token
        except Exception as e:
            logger.error(f"Failed to get refresh token: {e}")
            return None

    def delete_refresh_token(self, user_id: str) -> bool:
        """
        Delete refresh token for a user.

        Args:
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            logger.error("Redis client not available")
            return False

        try:
            key = f"refresh_token:{user_id}"
            self.redis_client.delete(key)
            logger.info(f"Refresh token deleted for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete refresh token: {e}")
            return False

    def add_to_blacklist(self, token: str, expires_in_seconds: int = 900) -> bool:
        """
        Add token to blacklist.

        Args:
            token: Token to blacklist
            expires_in_seconds: Expiration time in seconds (default: 15 min)

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            logger.error("Redis client not available")
            return False

        try:
            key = f"blacklist:{token}"
            self.redis_client.setex(key, expires_in_seconds, "1")
            logger.info("Token added to blacklist")
            return True
        except Exception as e:
            logger.error(f"Failed to add token to blacklist: {e}")
            return False

    def is_blacklisted(self, token: str) -> bool:
        """
        Check if token is blacklisted.

        Args:
            token: Token to check

        Returns:
            True if blacklisted, False otherwise
        """
        if not self.redis_client:
            logger.error("Redis client not available")
            return False

        try:
            key = f"blacklist:{token}"
            return self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Failed to check blacklist: {e}")
            return False


# Global Redis client instance
redis_client = RedisClient()
