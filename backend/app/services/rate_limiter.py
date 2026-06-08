import math
import time
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import RateLimitExceeded
from app.core.redis import get_redis_client

RATE_LIMIT_KEY_PREFIX = "rate_limit"

# Atomic token-bucket check + consume (Redis HASH: tokens, last_refill)
_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if tokens == nil then
  tokens = capacity
  last_refill = now
end

local elapsed = math.max(0, now - last_refill)
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens < cost then
  redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
  redis.call('EXPIRE', key, tonumber(ARGV[5]))
  return {0, tokens}
end

tokens = tokens - cost
redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, tonumber(ARGV[5]))
return {1, tokens}
"""


def user_messages_rate_key(user_id: UUID | str) -> str:
    """Pattern: rate_limit:{user_id}:messages"""
    return f"{RATE_LIMIT_KEY_PREFIX}:{user_id}:messages"


def ip_requests_rate_key(ip: str) -> str:
    """Pattern: rate_limit:{ip}:requests"""
    return f"{RATE_LIMIT_KEY_PREFIX}:{ip}:requests"


class RateLimiterService:
    """Token bucket rate limiter backed by Redis."""

    WINDOW_SECONDS = 60

    def __init__(self) -> None:
        self._redis = get_redis_client()
        self._script = self._redis.register_script(_TOKEN_BUCKET_LUA)

    async def _consume(self, key: str, *, limit: int, cost: int = 1) -> tuple[bool, float]:
        capacity = float(limit)
        refill_rate = capacity / self.WINDOW_SECONDS
        ttl = self.WINDOW_SECONDS * 2
        now = time.time()

        allowed, remaining = await self._script(
            keys=[key],
            args=[capacity, refill_rate, now, cost, ttl],
        )
        return bool(allowed), float(remaining)

    def _retry_after(self, remaining: float, limit: int) -> int:
        if remaining >= 1:
            return 0
        refill_rate = limit / self.WINDOW_SECONDS
        needed = 1 - remaining
        return max(1, math.ceil(needed / refill_rate))

    async def check_user_message(self, user_id: UUID | str) -> tuple[bool, float]:
        limit = settings.rate_limit_user_messages_per_minute
        return await self._consume(user_messages_rate_key(user_id), limit=limit)

    async def check_ip_request(self, ip: str) -> tuple[bool, float]:
        limit = settings.rate_limit_ip_requests_per_minute
        return await self._consume(ip_requests_rate_key(ip), limit=limit)

    async def enforce_user_message(self, user_id: UUID | str) -> None:
        limit = settings.rate_limit_user_messages_per_minute
        allowed, remaining = await self.check_user_message(user_id)
        if not allowed:
            raise RateLimitExceeded(
                limit=limit,
                window_seconds=self.WINDOW_SECONDS,
                retry_after_seconds=self._retry_after(remaining, limit),
                remaining=remaining,
                scope="user_messages",
                message="Too many messages. Please wait before sending again.",
            )

    async def enforce_ip_request(self, ip: str) -> None:
        limit = settings.rate_limit_ip_requests_per_minute
        allowed, remaining = await self.check_ip_request(ip)
        if not allowed:
            raise RateLimitExceeded(
                limit=limit,
                window_seconds=self.WINDOW_SECONDS,
                retry_after_seconds=self._retry_after(remaining, limit),
                remaining=remaining,
                scope="ip_requests",
                message="Too many requests from this IP address. Please slow down.",
            )
