from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message, SenderType
from app.schemas.chat_memory import ChatMemoryMessage, ChatMemoryRole


def sender_type_to_role(sender: SenderType) -> ChatMemoryRole:
    if sender == SenderType.customer:
        return ChatMemoryRole.customer
    if sender == SenderType.human_agent:
        return ChatMemoryRole.human_agent
    return ChatMemoryRole.ai


def role_to_sender_type(role: ChatMemoryRole) -> SenderType:
    if role == ChatMemoryRole.customer:
        return SenderType.customer
    if role == ChatMemoryRole.human_agent:
        return SenderType.human_agent
    return SenderType.ai


class MessageStoreService:
    async def persist(
        self,
        db: AsyncSession,
        *,
        conversation_id: UUID,
        role: ChatMemoryRole,
        content: str,
        language: str = "en",
        timestamp: datetime | None = None,
    ) -> Message:
        ts = timestamp or datetime.now(UTC).replace(tzinfo=None)
        message = Message(
            conversation_id=conversation_id,
            sender_type=role_to_sender_type(role),
            message=content,
            language=language,
            timestamp=ts,
        )
        db.add(message)
        await db.flush()
        return message

    async def fetch_last_messages(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        *,
        limit: int = 10,
    ) -> list[ChatMemoryMessage]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.timestamp))
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return [
            ChatMemoryMessage(
                role=sender_type_to_role(row.sender_type),
                content=row.message,
                timestamp=row.timestamp.replace(tzinfo=UTC)
                if row.timestamp.tzinfo is None
                else row.timestamp,
            )
            for row in rows
        ]

    async def get_last_activity(
        self,
        db: AsyncSession,
        conversation_id: UUID,
    ) -> datetime | None:
        stmt = (
            select(Message.timestamp)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.timestamp))
            .limit(1)
        )
        result = await db.execute(stmt)
        ts = result.scalar_one_or_none()
        if ts is None:
            return None
        return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts

    async def count_messages(
        self,
        db: AsyncSession,
        conversation_id: UUID,
    ) -> int:
        stmt = select(Message.id).where(Message.conversation_id == conversation_id)
        result = await db.execute(stmt)
        return len(result.all())

    async def verify_conversation_owner(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        user_id: UUID,
    ) -> Conversation | None:
        conversation = await db.get(Conversation, conversation_id)
        if conversation is None or conversation.user_id != user_id:
            return None
        return conversation
