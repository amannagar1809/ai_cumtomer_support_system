"""Email rate limiting service (50 per day per sender)."""

import logging
from datetime import datetime, timedelta

from app.core.redis import get_redis_client
from app.schemas.email import EmailRateLimitInfo

logger = logging.getLogger(__name__)


class EmailRateLimiter:
    """Rate limiter for email sending (50 per day per sender)."""

    def __init__(self):
        self.limit_per_day = 50
        self.key_prefix = "email_rate_limit"

    async def check_rate_limit(self, email: str) -> EmailRateLimitInfo:
        """
        Check if email sender is within rate limit.

        Args:
            email: Sender email address

        Returns:
            Rate limit information
        """
        redis = await get_redis_client()
        key = f"{self.key_prefix}:{email}"

        try:
            # Get current count
            count = await redis.incr(key)

            # Set expiry on first increment (24 hours)
            if count == 1:
                await redis.expire(key, 86400)  # 24 hours in seconds

            # Calculate reset time
            ttl = await redis.ttl(key)
            reset_at = datetime.utcnow() + timedelta(seconds=ttl)

            remaining = max(0, self.limit_per_day - count)

            return EmailRateLimitInfo(
                email=email,
                sent_today=count,
                limit=self.limit_per_day,
                remaining=remaining,
                reset_at=reset_at,
            )

        except Exception as e:
            logger.exception(f"Error checking rate limit for {email}: {e}")
            # Fail open - allow the email if Redis fails
            return EmailRateLimitInfo(
                email=email,
                sent_today=0,
                limit=self.limit_per_day,
                remaining=self.limit_per_day,
                reset_at=datetime.utcnow() + timedelta(days=1),
            )

    async def is_allowed(self, email: str) -> bool:
        """
        Check if email is allowed to be sent.

        Args:
            email: Sender email address

        Returns:
            True if within rate limit, False otherwise
        """
        rate_info = await self.check_rate_limit(email)
        return rate_info.remaining > 0

    async def increment_count(self, email: str) -> int:
        """
        Increment the email count for a sender.

        Args:
            email: Sender email address

        Returns:
            New count
        """
        redis = await get_redis_client()
        key = f"{self.key_prefix}:{email}"

        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 86400)
            return count
        except Exception as e:
            logger.exception(f"Error incrementing rate limit for {email}: {e}")
            return 0

    async def reset_count(self, email: str) -> None:
        """
        Reset the email count for a sender (admin function).

        Args:
            email: Sender email address
        """
        redis = await get_redis_client()
        key = f"{self.key_prefix}:{email}"

        try:
            await redis.delete(key)
            logger.info(f"Reset rate limit for {email}")
        except Exception as e:
            logger.exception(f"Error resetting rate limit for {email}: {e}")

    async def get_count(self, email: str) -> int:
        """
        Get the current email count for a sender.

        Args:
            email: Sender email address

        Returns:
            Current count
        """
        redis = await get_redis_client()
        key = f"{self.key_prefix}:{email}"

        try:
            count = await redis.get(key)
            return int(count) if count else 0
        except Exception as e:
            logger.exception(f"Error getting rate limit count for {email}: {e}")
            return 0
