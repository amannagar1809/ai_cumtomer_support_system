from uuid import UUID

from app.core.config import settings
from app.core.redis import get_chat_memory_redis_client
from app.schemas.chat_memory import ChatMemoryMessage, ChatMemoryState

CHAT_MEMORY_KEY_PREFIX = "chat_memory"


def chat_memory_key(conversation_id: UUID | str) -> str:
    """Pattern: chat_memory:{conversation_id}:messages"""
    return f"{CHAT_MEMORY_KEY_PREFIX}:{conversation_id}:messages"


class ChatMemoryService:
    """
    Active conversation transcript in Redis DB 1.
    Sliding window: TTL resets on every append (30 min default).
    """

    def __init__(self) -> None:
        self._redis = get_chat_memory_redis_client()
        self._ttl = settings.redis_chat_memory_ttl_seconds

    async def append_message(
        self,
        conversation_id: UUID | str,
        message: ChatMemoryMessage,
    ) -> int:
        """Add message and reset expiration (sliding window). Returns list length."""
        key = chat_memory_key(conversation_id)
        length = await self._redis.rpush(key, message.model_dump_json())
        await self._redis.expire(key, self._ttl)
        return length

    async def get_messages(self, conversation_id: UUID | str) -> ChatMemoryState:
        key = chat_memory_key(conversation_id)
        raw_messages = await self._redis.lrange(key, 0, -1)
        messages = [ChatMemoryMessage.model_validate_json(item) for item in raw_messages]
        return ChatMemoryState(
            conversation_id=str(conversation_id),
            messages=messages,
        )

    async def touch(self, conversation_id: UUID | str) -> bool:
        """Extend TTL without adding a message (e.g. typing indicator heartbeat)."""
        key = chat_memory_key(conversation_id)
        exists = await self._redis.exists(key)
        if not exists:
            return False
        await self._redis.expire(key, self._ttl)
        return True

    async def ttl_seconds(self, conversation_id: UUID | str) -> int:
        """Remaining TTL; -2 if key missing, -1 if no expiry."""
        return await self._redis.ttl(chat_memory_key(conversation_id))

    async def clear(self, conversation_id: UUID | str) -> bool:
        deleted = await self._redis.delete(chat_memory_key(conversation_id))
        return deleted > 0
