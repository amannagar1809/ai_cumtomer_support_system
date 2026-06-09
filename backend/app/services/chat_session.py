from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.conversation import Conversation, ConversationChannel, ConversationStatus
from app.models.user import CustomerType, User
from app.schemas.chat import (
    ChatGreetingMessage,
    ChatSessionMetadata,
    ChatSessionResponse,
    ChatSessionStatusResponse,
    ContinueConversationResponse,
    ConversationMessageResponse,
    ConversationMessagesResponse,
    CreateChatSessionRequest,
    ReturningUserResponse,
    SendMessageResponse,
)
from app.models.message import Message
from app.schemas.chat_memory import ChatMemoryMessage, ChatMemoryRole
from app.schemas.session import UserContext
from app.schemas.upload import MessageAttachment
from app.services.chat_memory import ChatMemoryService
from app.services.langgraph_attachments import LangGraphAttachmentService
from app.services.message_store import MessageStoreService
from app.services.session_cache import SessionCacheService
from app.services.user_context_cache import UserContextCacheService


def anonymous_email(anonymous_user_id: UUID) -> str:
    return f"anon-{anonymous_user_id}@guest.local"


class ChatSessionService:
    def __init__(self) -> None:
        self._sessions = SessionCacheService()
        self._chat_memory = ChatMemoryService()
        self._user_context = UserContextCacheService()
        self._messages = MessageStoreService()

    def _greeting_text(self, metadata: ChatSessionMetadata) -> str:
        locale = metadata.locale.lower()
        if locale.startswith("es"):
            return "Hola. Estamos aqui para ayudarte. En que podemos asistirte hoy?"
        return settings.chat_greeting_message

    def _expires_at(self, last_activity: datetime) -> datetime:
        return last_activity + timedelta(seconds=settings.redis_session_ttl_seconds)

    def _to_message_response(self, msg: ChatMemoryMessage) -> ConversationMessageResponse:
        return ConversationMessageResponse(
            role=msg.role.value,
            content=msg.content,
            timestamp=msg.timestamp,
        )

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

    async def _get_latest_conversation(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> Conversation | None:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.started_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _persist_and_cache_message(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        role: ChatMemoryRole,
        content: str,
        *,
        language: str = "en",
        timestamp: datetime | None = None,
        attachments: list[MessageAttachment] | None = None,
    ) -> tuple[Message, ChatMemoryMessage]:
        ts = timestamp or datetime.now(UTC)
        attachment_list = attachments or []
        display_content = MessageStoreService.format_content_with_attachments(
            content,
            attachment_list,
        )
        row = await self._messages.persist(
            db,
            conversation_id=conversation_id,
            role=role,
            content=content,
            language=language,
            timestamp=ts.replace(tzinfo=None),
            attachments=attachment_list,
        )
        memory_message = ChatMemoryMessage(
            role=role,
            content=display_content,
            timestamp=ts,
        )
        await self._chat_memory.append_message(conversation_id, memory_message)
        return row, memory_message

    async def _append_greeting(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        content: str,
        *,
        language: str = "en",
    ) -> ChatGreetingMessage:
        _row, message = await self._persist_and_cache_message(
            db,
            conversation_id,
            ChatMemoryRole.ai,
            content,
            language=language,
        )
        return ChatGreetingMessage(content=message.content, timestamp=message.timestamp)

    async def _get_recent_messages(
        self,
        db: AsyncSession,
        conversation_id: UUID,
    ) -> list[ChatMemoryMessage]:
        limit = settings.chat_history_message_limit
        memory = await self._chat_memory.get_messages(conversation_id)
        if memory.messages:
            return memory.messages[-limit:]
        return await self._messages.fetch_last_messages(
            db,
            conversation_id,
            limit=limit,
        )

    async def _hydrate_context(
        self,
        db: AsyncSession,
        user: User,
        conversation_id: UUID,
    ) -> list[ChatMemoryMessage]:
        """Load last messages into Redis and user context before the customer types."""
        messages = await self._messages.fetch_last_messages(
            db,
            conversation_id,
            limit=settings.chat_history_message_limit,
        )
        await self._chat_memory.load_messages(conversation_id, messages)
        await self._user_context.preload_on_conversation_start(
            user.id,
            conversation_id,
            db,
        )
        return messages

    async def get_returning_user_status(
        self,
        db: AsyncSession,
        anonymous_user_id: UUID,
    ) -> ReturningUserResponse:
        user = await self._get_user_by_anonymous_id(db, anonymous_user_id)
        if user is None:
            return ReturningUserResponse(is_returning_user=False)

        conversation = await self._get_latest_conversation(db, user.id)
        if conversation is None:
            return ReturningUserResponse(is_returning_user=False)

        message_count = await self._messages.count_messages(db, conversation.id)
        if message_count == 0:
            return ReturningUserResponse(is_returning_user=False)

        last_active = await self._messages.get_last_activity(db, conversation.id)
        if last_active is None:
            last_active = conversation.started_at.replace(tzinfo=UTC)

        return ReturningUserResponse(
            is_returning_user=True,
            conversation_id=conversation.id,
            last_active_at=last_active,
            message_count=message_count,
            can_continue=True,
        )

    async def continue_conversation(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        anonymous_user_id: UUID,
    ) -> ContinueConversationResponse | None:
        user = await self._get_user_by_anonymous_id(db, anonymous_user_id)
        if user is None:
            return None

        conversation = await self._messages.verify_conversation_owner(
            db,
            conversation_id,
            user.id,
        )
        if conversation is None:
            return None

        conversation.status = ConversationStatus.active
        conversation.ended_at = None

        messages = await self._hydrate_context(db, user, conversation_id)

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
            conversation_id=conversation_id,
        )
        await self._sessions.touch(user.id, session.session_id)

        last_active = await self._messages.get_last_activity(db, conversation_id)
        if last_active is None:
            last_active = conversation.started_at.replace(tzinfo=UTC)

        await db.commit()

        message_responses = await self._messages.fetch_last_message_responses(
            db,
            conversation_id,
            limit=settings.chat_history_message_limit,
        )
        return ContinueConversationResponse(
            session_id=session.session_id,
            conversation_id=conversation_id,
            anonymous_user_id=anonymous_user_id,
            expires_at=self._expires_at(session.last_activity),
            last_active_at=last_active,
            messages=message_responses,
            context_loaded=True,
        )

    async def get_conversation_messages(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        anonymous_user_id: UUID,
    ) -> ConversationMessagesResponse | None:
        user = await self._get_user_by_anonymous_id(db, anonymous_user_id)
        if user is None:
            return None

        conversation = await self._messages.verify_conversation_owner(
            db,
            conversation_id,
            user.id,
        )
        if conversation is None:
            return None

        messages = await self._messages.fetch_last_message_responses(
            db,
            conversation_id,
            limit=settings.chat_history_message_limit,
        )
        return ConversationMessagesResponse(
            conversation_id=conversation_id,
            messages=messages,
        )

    async def send_message(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        anonymous_user_id: UUID,
        content: str,
        *,
        session_id: UUID | None = None,
        attachments: list[MessageAttachment] | None = None,
    ) -> SendMessageResponse | None:
        user = await self._get_user_by_anonymous_id(db, anonymous_user_id)
        if user is None:
            return None

        conversation = await self._messages.verify_conversation_owner(
            db,
            conversation_id,
            user.id,
        )
        if conversation is None:
            return None

        attachment_list = attachments or []
        if not content.strip() and not attachment_list:
            raise ValueError("Message must include text or attachments")
        if len(attachment_list) > settings.upload_max_files_per_message:
            raise ValueError(
                f"Maximum {settings.upload_max_files_per_message} files per message"
            )

        row, _memory = await self._persist_and_cache_message(
            db,
            conversation_id,
            ChatMemoryRole.customer,
            content,
            language=user.language,
            attachments=attachment_list,
        )
        if attachment_list:
            await LangGraphAttachmentService().submit_for_processing(
                conversation_id=conversation_id,
                message_id=row.id,
                attachments=attachment_list,
            )
        if session_id:
            await self._sessions.touch(user.id, session_id)
        await db.commit()

        return SendMessageResponse(
            message=self._messages.message_to_response(
                row,
                role=ChatMemoryRole.customer.value,
            )
        )

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

        await self._hydrate_context(db, user, conversation_id)

        messages = await self._get_recent_messages(db, conversation_id)
        if messages:
            first = messages[0]
            greeting = ChatGreetingMessage(
                content=first.content,
                timestamp=first.timestamp,
            )
        else:
            greeting = await self._append_greeting(
                db,
                conversation_id,
                settings.chat_greeting_message,
                language=user.language,
            )
            await db.commit()

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
        greeting = await self._append_greeting(
            db,
            conversation.id,
            greeting_text,
            language=user.language[:2],
        )

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

        messages = await self._get_recent_messages(db, session.conversation_id)
        if messages:
            first = messages[0]
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
