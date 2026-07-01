"""Redis-based rate limiter with sliding window algorithm."""

import logging
import time
from typing import Optional

from app.core.config import settings
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-based rate limiter using sliding window algorithm."""

    def __init__(self):
        """Initialize rate limiter."""
        self.redis = redis_client
        self.logger = logger

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int]:
        """
        Check if request is allowed using sliding window algorithm.

        Args:
            key: Unique identifier for the rate limit (user_id, ip_address, etc.)
            limit: Maximum number of requests allowed
            window: Time window in seconds

        Returns:
            Tuple of (is_allowed, retry_after)
        """
        try:
            current_time = int(time.time())
            window_start = current_time - window

            # Remove old entries outside the window
            await self.redis.client.zremrangebyscore(key, 0, window_start)

            # Count current requests in window
            current_count = await self.redis.client.zcard(key)

            # Check if limit exceeded
            if current_count >= limit:
                # Get oldest timestamp to calculate retry_after
                oldest = await self.redis.client.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_timestamp = int(oldest[0][1])
                    retry_after = oldest_timestamp + window - current_time
                    return False, max(1, retry_after)
                return False, window

            # Add current request timestamp
            await self.redis.client.zadd(key, {str(current_time): current_time})

            # Set expiry on the key
            await self.redis.client.expire(key, window + 1)

            return True, 0

        except Exception as e:
            self.logger.error(f"Rate limiter error: {e}")
            # Fail open - allow request if rate limiter fails
            return True, 0

    async def get_current_count(self, key: str, window: int) -> int:
        """
        Get current request count for a key.

        Args:
            key: Unique identifier
            window: Time window in seconds

        Returns:
            Current request count
        """
        try:
            current_time = int(time.time())
            window_start = current_time - window

            # Remove old entries outside the window
            await self.redis.client.zremrangebyscore(key, 0, window_start)

            # Count current requests in window
            return await self.redis.client.zcard(key)

        except Exception as e:
            self.logger.error(f"Failed to get current count: {e}")
            return 0

    async def reset(self, key: str) -> bool:
        """
        Reset rate limit for a key.

        Args:
            key: Unique identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.redis.client.delete(key)
            return True
        except Exception as e:
            self.logger.error(f"Failed to reset rate limit: {e}")
            return False


class RateLimitConfig:
    """Rate limit configuration."""

    @property
    def USER_PER_MINUTE(self) -> int:
        return getattr(settings, 'rate_limit_user_per_minute', 60)

    @property
    def USER_PER_HOUR(self) -> int:
        return getattr(settings, 'rate_limit_user_per_hour', 1000)

    @property
    def IP_PER_MINUTE(self) -> int:
        return getattr(settings, 'rate_limit_ip_per_minute', 120)

    @property
    def IP_PER_HOUR(self) -> int:
        return getattr(settings, 'rate_limit_ip_per_hour', 2000)

    @property
    def AUTH_PER_MINUTE(self) -> int:
        return getattr(settings, 'rate_limit_auth_per_minute', 5)

    @property
    def AUTH_PER_HOUR(self) -> int:
        return getattr(settings, 'rate_limit_auth_per_hour', 50)

    @property
    def API_PER_MINUTE(self) -> int:
        return 100

    @property
    def API_PER_HOUR(self) -> int:
        return 5000

    @property
    def SUSTAINED_THRESHOLD(self) -> int:
        return getattr(settings, 'rate_limit_sustained_threshold', 10)


class RateLimitTracker:
    """Track rate limit hits for alerting."""

    def __init__(self):
        """Initialize rate limit tracker."""
        self.hit_counts = {}  # key -> consecutive hit count
        self.config = RateLimitConfig()
        self.logger = logger

    def record_hit(self, key: str) -> bool:
        """
        Record a rate limit hit and check if alert should be triggered.

        Args:
            key: Unique identifier (user_id, ip_address)

        Returns:
            True if alert should be triggered
        """
        if key not in self.hit_counts:
            self.hit_counts[key] = 0

        self.hit_counts[key] += 1

        if self.hit_counts[key] >= self.config.SUSTAINED_THRESHOLD:
            self.logger.warning(
                f"Sustained rate limit hits detected for {key}: "
                f"{self.hit_counts[key]} consecutive hits"
            )
            # Reset after alerting
            self.hit_counts[key] = 0
            return True

        return False

    def record_success(self, key: str):
        """
        Record a successful request (resets hit counter key).

        Args:
            key: Unique identifier
        """
        if key in self.hit_counts:
            self.hit_counts[key] = 0

    def cleanup_old_keys(self, max_age: int = 3600):
        """
        Clean up old keys from hit counts.

        Args:
            max_age: Maximum age in seconds (default: 1 hour)
        """
        # This is a simple in-memory cleanup
        # In production, consider using a more sophisticated approach
        pass


# Global instances
rate_limiter = RateLimiter()
rate_limit_tracker = RateLimitTracker()
