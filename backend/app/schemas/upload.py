from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class AttachmentType(str, Enum):
    image = "image"
    pdf = "pdf"
    text = "text"


class MessageAttachment(BaseModel):
    file_id: UUID
    url: str
    filename: str
    content_type: str
    attachment_type: AttachmentType
    size_bytes: int
    ocr_requested: bool = False


class InitUploadRequest(BaseModel):
    anonymous_user_id: UUID
    conversation_id: UUID
    filename: str
    content_type: str
    size_bytes: int


class ChunkUploadInfo(BaseModel):
    chunk_index: int
    upload_url: str
    method: str = "PUT"


class InitUploadResponse(BaseModel):
    upload_id: UUID
    file_id: UUID
    chunk_size: int
    total_chunks: int
    chunks: list[ChunkUploadInfo]
    storage_provider: str


class CompleteUploadRequest(BaseModel):
    anonymous_user_id: UUID
    conversation_id: UUID
    upload_id: UUID


class CompleteUploadResponse(BaseModel):
    file_id: UUID
    url: str
    filename: str
    content_type: str
    attachment_type: AttachmentType
    size_bytes: int
    preview_url: str | None = None


class UploadLimitsResponse(BaseModel):
    max_file_size_bytes: int
    max_files_per_message: int
    chunk_size_bytes: int
    allowed_extensions: list[str]
    allowed_content_types: list[str]


class LangGraphAttachmentPayload(BaseModel):
    """Payload forwarded to LangGraph for attachment processing."""

    conversation_id: UUID
    message_id: UUID | None = None
    attachments: list[MessageAttachment]
    queued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
