from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.conversation import Conversation, ConversationChannel, ConversationStatus
from app.models.user import CustomerType, User
from app.schemas.chat import (
    ChatGreetingMessage,
    ChatSessionMetadata,
    ChatSessionResponse,
    ChatSessionStatusResponse,
    CreateChatSessionRequest,
)
from app.schemas.chat_memory import ChatMemoryMessage, ChatMemoryRole
from app.schemas.session import UserContext
from app.services.chat_memory import ChatMemoryService
from app.services.session_cache import SessionCacheService
from app.services.user_context_cache import UserContextCacheService


def anonymous_email(anonymous_user_id: UUID) -> str:
    return f"anon-{anonymous_user_id}@guest.local"


class ChatSessionService:
    def __init__(self) -> None:
        self._sessions = SessionCacheService()
        self._chat_memory = ChatMemoryService()
        self._user_context = UserContextCacheService()

    def _greeting_text(self, metadata: ChatSessionMetadata) -> str:
        locale = metadata.locale.lower()
        if locale.startswith("es"):
            return "Hola. Estamos aqui para ayudarte. En que podemos asistirte hoy?"
        return settings.chat_greeting_message

    async def _get_user_by_anonymous_id(
        self,
        db: AsyncSession,
        anonymous_user_id: UUID,
    ) -> User | None:
        result = await db.execute(
            select(User).where(User.email == anonymous_email(anonymous_user_id))
        )
        return result.scalar_one_or_none()

    async def _get_or_create_guest_user(
        self,
        db: AsyncSession,
        anonymous_user_id: UUID,
        language: str,
    ) -> User:
        user = await self._get_user_by_anonymous_id(db, anonymous_user_id)
        if user:
            return user

        user = User(
            name="Guest",
            email=anonymous_email(anonymous_user_id),
            language=language[:2] if language else "en",
            customer_type=CustomerType.regular,
        )
        db.add(user)
        await db.flush()
        return user

    async def _append_greeting(
        self,
        conversation_id: UUID,
        content: str,
    ) -> ChatGreetingMessage:
        now = datetime.now(UTC)
        greeting = ChatGreetingMessage(content=content, timestamp=now)
        await self._chat_memory.append_message(
            conversation_id,
            ChatMemoryMessage(
                role=ChatMemoryRole.ai,
                content=content,
                timestamp=now,
            ),
        )
        return greeting

    def _expires_at(self, last_activity: datetime) -> datetime:
        return last_activity + timedelta(seconds=settings.redis_session_ttl_seconds)

    async def _resume_session(
        self,
        db: AsyncSession,
        anonymous_user_id: UUID,
        session_id: UUID,
        conversation_id: UUID,
    ) -> ChatSessionResponse | None:
        user = await self._get_user_by_anonymous_id(db, anonymous_user_id)
        if user is None:
            return None

        session = await self._sessions.get(user.id, session_id)
        if session is None or session.conversation_id != conversation_id:
            return None

        session = await self._sessions.touch(user.id, session_id)
        if session is None:
            return None

        memory = await self._chat_memory.get_messages(conversation_id)
        if memory.messages:
            first = memory.messages[0]
            greeting = ChatGreetingMessage(
                content=first.content,
                timestamp=first.timestamp,
            )
        else:
            greeting = await self._append_greeting(
                conversation_id,
                settings.chat_greeting_message,
            )

        return ChatSessionResponse(
            session_id=session.session_id,
            conversation_id=conversation_id,
            anonymous_user_id=anonymous_user_id,
            expires_at=self._expires_at(session.last_activity),
            greeting=greeting,
            resumed=True,
        )

    async def start_session(
        self,
        db: AsyncSession,
        request: CreateChatSessionRequest,
    ) -> ChatSessionResponse:
        anonymous_user_id = request.anonymous_user_id or uuid4()
        language = request.metadata.locale

        if (
            request.session_id
            and request.conversation_id
            and request.anonymous_user_id
        ):
            resumed = await self._resume_session(
                db,
                anonymous_user_id,
                request.session_id,
                request.conversation_id,
            )
            if resumed:
                return resumed

        user = await self._get_or_create_guest_user(db, anonymous_user_id, language)

        conversation = Conversation(
            user_id=user.id,
            channel=request.channel,
            status=ConversationStatus.active,
        )
        db.add(conversation)
        await db.flush()

        user_context = UserContext(
            user_id=user.id,
            email=user.email,
            name=user.name,
            customer_type=user.customer_type.value,
            language=user.language,
        )
        session = await self._sessions.create(
            user_context,
            permissions=["chat:read", "chat:write"],
            conversation_id=conversation.id,
        )
        await self._user_context.preload_on_conversation_start(
            user.id,
            conversation.id,
            db,
        )

        greeting_text = self._greeting_text(request.metadata)
        greeting = await self._append_greeting(conversation.id, greeting_text)

        await db.commit()

        return ChatSessionResponse(
            session_id=session.session_id,
            conversation_id=conversation.id,
            anonymous_user_id=anonymous_user_id,
            expires_at=self._expires_at(session.last_activity),
            greeting=greeting,
            resumed=False,
        )

    async def get_session_status(
        self,
        db: AsyncSession,
        session_id: UUID,
        anonymous_user_id: UUID,
    ) -> ChatSessionStatusResponse | None:
        user = await self._get_user_by_anonymous_id(db, anonymous_user_id)
        if user is None:
            return None

        session = await self._sessions.get(user.id, session_id)
        if session is None or session.conversation_id is None:
            return None

        memory = await self._chat_memory.get_messages(session.conversation_id)
        if memory.messages:
            first = memory.messages[0]
            greeting = ChatGreetingMessage(
                content=first.content,
                timestamp=first.timestamp,
            )
        else:
            greeting = ChatGreetingMessage(
                content=settings.chat_greeting_message,
                timestamp=session.last_activity,
            )

        return ChatSessionStatusResponse(
            session_id=session.session_id,
            conversation_id=session.conversation_id,
            anonymous_user_id=anonymous_user_id,
            expires_at=self._expires_at(session.last_activity),
            greeting=greeting,
        )
