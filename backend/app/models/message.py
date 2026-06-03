import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class SenderType(str, enum.Enum):
    customer = "customer"
    ai = "ai"
    human_agent = "human_agent"


class Message(Base):
    """
    Partitioned parent table (RANGE by timestamp).
    Monthly child partitions are created via DB function create_messages_partition().
    """

    __tablename__ = "messages"
    __table_args__ = (
        Index(
            "ix_messages_message_fts",
            text("to_tsvector('english', message)"),
            postgresql_using="gin",
        ),
        Index("ix_messages_conversation_id_timestamp", "conversation_id", "timestamp"),
        {"postgresql_partition_by": "RANGE (timestamp)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    timestamp: Mapped[datetime] = mapped_column(
        "timestamp",
        DateTime(timezone=False),
        primary_key=True,
        nullable=False,
        server_default=func.now(),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_type: Mapped[SenderType] = mapped_column(
        Enum(
            SenderType,
            name="message_sender_type",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, server_default="en")
    sentiment: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
