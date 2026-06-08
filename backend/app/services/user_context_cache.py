from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis_client
from app.models.conversation import Conversation
from app.models.ticket import Ticket, TicketStatus
from app.models.user import User
from app.schemas.user_context import UserContextCache

USER_CONTEXT_KEY_PREFIX = "user_context"


def user_context_key(user_id: UUID | str) -> str:
    """Pattern: user_context:{user_id}"""
    return f"{USER_CONTEXT_KEY_PREFIX}:{user_id}"


class UserContextCacheService:
    """Redis HASH user context on DB 0. TTL 7 days for returning users."""

    def __init__(self) -> None:
        self._redis = get_redis_client()
        self._ttl = settings.redis_user_context_ttl_seconds

    async def get(self, user_id: UUID) -> UserContextCache | None:
        data = await self._redis.hgetall(user_context_key(user_id))
        if not data:
            return None
        return UserContextCache.from_redis_hash(user_id, data)

    async def save(self, context: UserContextCache) -> UserContextCache:
        key = user_context_key(context.user_id)
        await self._redis.hset(key, mapping=context.to_redis_hash())
        await self._redis.expire(key, self._ttl)
        return context

    async def delete(self, user_id: UUID) -> bool:
        deleted = await self._redis.delete(user_context_key(user_id))
        return deleted > 0

    async def _load_from_db(
        self,
        user_id: UUID,
        db: AsyncSession,
    ) -> tuple[str, list[UUID]]:
        user = await db.get(User, user_id)
        preferred_language = user.language if user else "en"

        stmt = (
            select(Ticket.id)
            .join(Conversation, Ticket.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user_id,
                Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress]),
            )
        )
        result = await db.execute(stmt)
        active_ticket_ids = list(result.scalars().all())
        return preferred_language, active_ticket_ids

    async def preload_on_conversation_start(
        self,
        user_id: UUID,
        conversation_id: UUID,
        db: AsyncSession,
    ) -> UserContextCache:
        """
        Load user context into Redis when a conversation starts.
        Merges cached sentiment_trend; refreshes language, tickets, last conversation.
        """
        existing = await self.get(user_id)
        preferred_language, active_ticket_ids = await self._load_from_db(user_id, db)

        context = UserContextCache(
            user_id=user_id,
            preferred_language=preferred_language,
            last_conversation_id=conversation_id,
            sentiment_trend=existing.sentiment_trend if existing else [],
            active_ticket_ids=active_ticket_ids,
        )
        return await self.save(context)
