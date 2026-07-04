from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.uuid import uuid7
from app.models.conversation import Conversation
from app.models.message import Message, SenderType
from app.schemas.chat import ConversationMessageResponse
from app.schemas.chat_memory import ChatMemoryMessage, ChatMemoryRole
from app.schemas.upload import MessageAttachment


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
    REDACTED_MESSAGE = "[redacted]"

    @staticmethod
    def format_content_with_attachments(
        content: str,
        attachments: list[MessageAttachment],
    ) -> str:
        if not attachments:
            return content
        names = ", ".join(a.filename for a in attachments)
        attachment_note = f"[Attachments: {names}]"
        return f"{content}\n{attachment_note}".strip() if content else attachment_note

    @staticmethod
    def attachments_from_metadata(metadata: dict[str, Any] | None) -> list[MessageAttachment]:
        if not metadata:
            return []
        raw = metadata.get("attachments", [])
        return [MessageAttachment.model_validate(item) for item in raw]

    async def persist(
        self,
        db: AsyncSession,
        *,
        conversation_id: UUID,
        role: ChatMemoryRole,
        content: str,
        language: str = "en",
        timestamp: datetime | None = None,
        attachments: list[MessageAttachment] | None = None,
    ) -> Message:
        ts = timestamp or datetime.now(UTC).replace(tzinfo=None)
        attachment_list = attachments or []
        if len(attachment_list) > settings.upload_max_files_per_message:
            raise ValueError(
                f"Maximum {settings.upload_max_files_per_message} files per message"
            )
        metadata: dict[str, Any] | None = None
        if attachment_list:
            metadata = {
                "attachments": [a.model_dump(mode="json") for a in attachment_list]
            }
        message = Message(
            id=uuid7(),
            conversation_id=conversation_id,
            sender_type=role_to_sender_type(role),
            message=self.format_content_with_attachments(content, attachment_list),
            language=language,
            timestamp=ts,
            sentiment=metadata,
        )
        db.add(message)
        await db.flush()
        return message

    async def persist_batch(
        self,
        db: AsyncSession,
        messages: list[dict[str, Any]],
    ) -> list[Message]:
        """Persist many messages in one INSERT statement for high-volume flows."""
        if not messages:
            return []

        rows: list[dict[str, Any]] = []
        for item in messages:
            raw_attachments = item.get("attachments") or []
            if len(raw_attachments) > settings.upload_max_files_per_message:
                raise ValueError(
                    f"Maximum {settings.upload_max_files_per_message} files per message"
                )
            attachments = [
                attachment
                if isinstance(attachment, MessageAttachment)
                else MessageAttachment.model_validate(attachment)
                for attachment in raw_attachments
            ]
            timestamp = item.get("timestamp") or datetime.now(UTC).replace(tzinfo=None)
            if timestamp.tzinfo is not None:
                timestamp = timestamp.replace(tzinfo=None)

            metadata: dict[str, Any] | None = None
            if attachments:
                metadata = {
                    "attachments": [
                        attachment.model_dump(mode="json")
                        for attachment in attachments
                    ]
                }

            rows.append(
                {
                    "id": uuid7(),
                    "conversation_id": item["conversation_id"],
                    "sender_type": role_to_sender_type(item["role"]),
                    "message": self.format_content_with_attachments(
                        item.get("content", ""),
                        attachments,
                    ),
                    "language": item.get("language", "en"),
                    "timestamp": timestamp,
                    "sentiment": metadata,
                }
            )

        result = await db.execute(insert(Message).returning(Message), rows)
        return list(result.scalars().all())

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
                id=row.id,
                role=sender_type_to_role(row.sender_type),
                content=row.message,
                timestamp=row.timestamp.replace(tzinfo=UTC)
                if row.timestamp.tzinfo is None
                else row.timestamp,
            )
            for row in rows
        ]

    async def fetch_last_message_responses(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        *,
        limit: int = 10,
    ) -> list[ConversationMessageResponse]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.timestamp))
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return [self.message_to_response(row) for row in rows]

    def message_to_response(
        self,
        row: Message,
        *,
        role: str | None = None,
    ) -> ConversationMessageResponse:
        attachments = self.attachments_from_metadata(row.sentiment)
        return ConversationMessageResponse(
            id=row.id,
            role=role or sender_type_to_role(row.sender_type).value,
            content=row.message,
            timestamp=row.timestamp.replace(tzinfo=UTC)
            if row.timestamp.tzinfo is None
            else row.timestamp,
            attachments=attachments,
        )

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
        stmt = select(func.count()).select_from(Message).where(
            Message.conversation_id == conversation_id
        )
        result = await db.execute(stmt)
        return int(result.scalar_one())

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

    async def redact_message(
        self,
        db: AsyncSession,
        *,
        conversation_id: UUID,
        message_id: UUID,
        reason: str,
    ) -> Message | None:
        stmt = select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation_id,
        )
        result = await db.execute(stmt)
        message = result.scalar_one_or_none()
        if message is None:
            return None

        now = datetime.now(UTC).replace(tzinfo=None)
        message.message = self.REDACTED_MESSAGE
        message.sentiment = {
            "redacted": True,
            "redacted_at": now.isoformat(),
        }
        message.redacted_at = now
        message.redaction_reason = reason[:255]
        await db.flush()
        return message
