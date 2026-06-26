"""Knowledge base document model for multi-language support."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Index,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

if TYPE_CHECKING:
    pass


class DocumentLanguage(str, enum.Enum):
    """Supported languages for knowledge base documents."""

    en = "en"
    hi = "hi"
    es = "es"
    fr = "fr"
    ar = "ar"
    de = "de"


class KnowledgeBaseDocument(Base):
    """Knowledge base document with multi-language support."""

    __tablename__ = "knowledge_base_documents"
    __table_args__ = (
        CheckConstraint(
            "title IS NOT NULL AND title != ''",
            name="ck_knowledge_base_documents_title_not_empty",
        ),
        CheckConstraint(
            "content IS NOT NULL AND content != ''",
            name="ck_knowledge_base_documents_content_not_empty",
        ),
        Index("ix_knowledge_base_documents_language", "language"),
        Index(".ix_knowledge_base_documents_category", "category"),
        Index("ix_knowledge_base_documents_original_document_id", "original_document_id"),
        Index("ix_knowledge_base_documents_language_original_id", "language", "original_document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    original_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
    )  # Links to original English document
    language: Mapped[DocumentLanguage] = mapped_column(
        Enum(
            DocumentLanguage,
            name="document_language",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        server_default=DocumentLanguage.en.value,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(
        Text, nullable=True
    )  # JSON array of tags
    metadata: Mapped[dict | None] = mapped_column(
        Text, nullable=True
    )  # JSON metadata
    is_original: Mapped[bool] = mapped_column(
        nullable=False,
        server_default="true",
    )  # True for original English document
    is_translated: Mapped[bool] = mapped_column(
        nullable=False,
        server_default="false",
    )  # True for translated versions
    translation_confidence: Mapped[float | None] = mapped_column(
        nullable=True
    )  # Translation quality score (0-1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
