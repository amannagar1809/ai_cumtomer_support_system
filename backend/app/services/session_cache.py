from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.config import settings
from app.core.redis import get_redis_client
from app.schemas.session import SessionData, SessionMetadata, UserContext

SESSION_KEY_PREFIX = "session"


def session_key(user_id: UUID, session_id: UUID) -> str:
    """Pattern: session:{user_id}:{session_id}"""
    return f"{SESSION_KEY_PREFIX}:{user_id}:{session_id}"


def user_session_pattern(user_id: UUID) -> str:
    return f"{SESSION_KEY_PREFIX}:{user_id}:*"


class SessionCacheService:
    def __init__(self) -> None:
        self._redis = get_redis_client()
        self._ttl = settings.redis_session_ttl_seconds

    async def create(
        self,
        user_context: UserContext,
        permissions: list[str] | None = None,
        session_id: UUID | None = None,
        conversation_id: UUID | None = None,
        metadata: SessionMetadata | None = None,
    ) -> SessionData:
        sid = session_id or uuid4()
        now = datetime.now(UTC)
        session = SessionData(
            session_id=sid,
            user_context=user_context,
            last_activity=now,
            permissions=permissions or [],
            conversation_id=conversation_id,
            metadata=metadata or SessionMetadata(),
        )
        key = session_key(user_context.user_id, sid)
        await self._redis.set(key, session.model_dump_json(), ex=self._ttl)
        return session

    async def get(self, user_id: UUID, session_id: UUID) -> SessionData | None:
        raw = await self._redis.get(session_key(user_id, session_id))
        if raw is None:
            return None
        session = SessionData.model_validate_json(raw)
        if self._is_expired(session):
            await self.delete(user_id, session_id)
            return None
        return session

    async def touch(self, user_id: UUID, session_id: UUID) -> SessionData | None:
        """Refresh last_activity and extend TTL."""
        session = await self.get(user_id, session_id)
        if session is None:
            return None
        session.last_activity = datetime.now(UTC)
        key = session_key(user_id, session_id)
        await self._redis.set(key, session.model_dump_json(), ex=self._ttl)
        return session

    async def update_permissions(
        self,
        user_id: UUID,
        session_id: UUID,
        permissions: list[str],
    ) -> SessionData | None:
        session = await self.get(user_id, session_id)
        if session is None:
            return None
        session.permissions = permissions
        session.last_activity = datetime.now(UTC)
        key = session_key(user_id, session_id)
        await self._redis.set(key, session.model_dump_json(), ex=self._ttl)
        return session

    async def transfer(
        self,
        *,
        from_user_id: UUID,
        to_user_context: UserContext,
        session_id: UUID,
    ) -> SessionData | None:
        session = await self.get(from_user_id, session_id)
        if session is None:
            return None

        now = datetime.now(UTC)
        session.user_context = to_user_context
        session.last_activity = now
        session.metadata.authenticated_user_id = to_user_context.user_id
        session.metadata.is_authenticated = True

        old_key = session_key(from_user_id, session_id)
        new_key = session_key(to_user_context.user_id, session_id)
        await self._redis.set(new_key, session.model_dump_json(), ex=self._ttl)
        await self._redis.delete(old_key)
        return session

    async def delete(self, user_id: UUID, session_id: UUID) -> bool:
        deleted = await self._redis.delete(session_key(user_id, session_id))
        return deleted > 0

    async def delete_all_for_user(self, user_id: UUID) -> int:
        keys = [key async for key in self._redis.scan_iter(match=user_session_pattern(user_id))]
        if not keys:
            return 0
        return await self._redis.delete(*keys)

    async def cleanup_expired_sessions(self) -> int:
        deleted = 0
        pattern = f"{SESSION_KEY_PREFIX}:*:*"
        async for key in self._redis.scan_iter(match=pattern):
            raw = await self._redis.get(key)
            if raw is None:
                continue
            try:
                session = SessionData.model_validate_json(raw)
            except ValueError:
                deleted += await self._redis.delete(key)
                continue
            if self._is_expired(session):
                deleted += await self._redis.delete(key)
        return deleted

    def _is_expired(self, session: SessionData) -> bool:
        last_activity = session.last_activity
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=UTC)
        return datetime.now(UTC) - last_activity > timedelta(seconds=self._ttl)
