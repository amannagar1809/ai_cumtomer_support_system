from collections.abc import AsyncGenerator

import redis.asyncio as redis

from app.core.config import settings

_redis_client: redis.Redis | None = None
_chat_memory_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Redis DB 0 — sessions, rate limits, general cache."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


def get_chat_memory_redis_client() -> redis.Redis:
    """Redis DB 1 — active chat transcripts."""
    global _chat_memory_client
    if _chat_memory_client is None:
        _chat_memory_client = redis.from_url(
            settings.redis_chat_memory_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _chat_memory_client


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    yield get_redis_client()


async def close_redis() -> None:
    global _redis_client, _chat_memory_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
    if _chat_memory_client is not None:
        await _chat_memory_client.aclose()
        _chat_memory_client = None
