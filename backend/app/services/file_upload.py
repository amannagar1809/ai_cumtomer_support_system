import json
import math
from pathlib import Path
from uuid import UUID, uuid4

from app.core.config import settings
from app.core.redis import get_redis_client
from app.schemas.upload import (
    AttachmentType,
    ChunkUploadInfo,
    CompleteUploadResponse,
    InitUploadRequest,
    InitUploadResponse,
    UploadLimitsResponse,
)
from app.services.storage.factory import get_storage_backend

UPLOAD_KEY_PREFIX = "upload"

ALLOWED_CONTENT_TYPES: dict[str, AttachmentType] = {
    "image/jpeg": AttachmentType.image,
    "image/jpg": AttachmentType.image,
    "image/png": AttachmentType.image,
    "application/pdf": AttachmentType.pdf,
    "text/plain": AttachmentType.text,
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".txt"}


class FileUploadError(ValueError):
    pass


class FileUploadService:
    def __init__(self) -> None:
        self._redis = get_redis_client()
        self._storage = get_storage_backend()

    def limits(self) -> UploadLimitsResponse:
        return UploadLimitsResponse(
            max_file_size_bytes=settings.upload_max_file_size_bytes,
            max_files_per_message=settings.upload_max_files_per_message,
            chunk_size_bytes=settings.upload_chunk_size_bytes,
            allowed_extensions=sorted(ALLOWED_EXTENSIONS),
            allowed_content_types=sorted(ALLOWED_CONTENT_TYPES.keys()),
        )

    def _upload_key(self, upload_id: UUID) -> str:
        return f"{UPLOAD_KEY_PREFIX}:{upload_id}"

    def _attachment_type(self, content_type: str, filename: str) -> AttachmentType:
        normalized = content_type.lower().split(";")[0].strip()
        if normalized in ALLOWED_CONTENT_TYPES:
            return ALLOWED_CONTENT_TYPES[normalized]
        ext = Path(filename).suffix.lower()
        if ext in {".jpg", ".jpeg", ".png"}:
            return AttachmentType.image
        if ext == ".pdf":
            return AttachmentType.pdf
        if ext == ".txt":
            return AttachmentType.text
        raise FileUploadError(f"File type not allowed: {content_type}")

    def validate_file(self, *, filename: str, content_type: str, size_bytes: int) -> None:
        if size_bytes <= 0:
            raise FileUploadError("File is empty")
        if size_bytes > settings.upload_max_file_size_bytes:
            raise FileUploadError(
                f"File exceeds {settings.upload_max_file_size_bytes // (1024 * 1024)}MB limit"
            )
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise FileUploadError(
                f"Extension '{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        normalized = content_type.lower().split(";")[0].strip()
        if normalized not in ALLOWED_CONTENT_TYPES:
            raise FileUploadError(
                f"Content type '{content_type}' not allowed"
            )
        self._attachment_type(content_type, filename)

    async def init_upload(self, request: InitUploadRequest) -> InitUploadResponse:
        self.validate_file(
            filename=request.filename,
            content_type=request.content_type,
            size_bytes=request.size_bytes,
        )

        upload_id = uuid4()
        file_id = uuid4()
        chunk_size = settings.upload_chunk_size_bytes
        total_chunks = max(1, math.ceil(request.size_bytes / chunk_size))

        chunks = await self._storage.create_chunk_targets(
            upload_id=upload_id,
            file_id=file_id,
            filename=request.filename,
            content_type=request.content_type,
            total_chunks=total_chunks,
        )

        session = {
            "upload_id": str(upload_id),
            "file_id": str(file_id),
            "filename": request.filename,
            "content_type": request.content_type,
            "size_bytes": request.size_bytes,
            "total_chunks": total_chunks,
            "conversation_id": str(request.conversation_id),
            "anonymous_user_id": str(request.anonymous_user_id),
        }
        await self._redis.set(
            self._upload_key(upload_id),
            json.dumps(session),
            ex=settings.upload_signed_url_ttl_seconds,
        )

        return InitUploadResponse(
            upload_id=upload_id,
            file_id=file_id,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            chunks=[
                ChunkUploadInfo(
                    chunk_index=c.chunk_index,
                    upload_url=c.upload_url,
                    method=c.method,
                )
                for c in chunks
            ],
            storage_provider=settings.storage_provider,
        )

    async def _get_session(self, upload_id: UUID) -> dict:
        raw = await self._redis.get(self._upload_key(upload_id))
        if not raw:
            raise FileUploadError("Upload session expired or not found")
        return json.loads(raw)

    async def store_chunk(
        self,
        upload_id: UUID,
        chunk_index: int,
        data: bytes,
        *,
        anonymous_user_id: UUID,
    ) -> None:
        session = await self._get_session(upload_id)
        if session["anonymous_user_id"] != str(anonymous_user_id):
            raise FileUploadError("Upload session does not belong to this user")
        if chunk_index < 0 or chunk_index >= session["total_chunks"]:
            raise FileUploadError("Invalid chunk index")
        await self._storage.store_chunk(
            upload_id=upload_id,
            chunk_index=chunk_index,
            data=data,
        )

    async def complete_upload(
        self,
        upload_id: UUID,
        *,
        anonymous_user_id: UUID,
        conversation_id: UUID,
    ) -> CompleteUploadResponse:
        session = await self._get_session(upload_id)
        if session["anonymous_user_id"] != str(anonymous_user_id):
            raise FileUploadError("Upload session does not belong to this user")
        if session["conversation_id"] != str(conversation_id):
            raise FileUploadError("Upload session does not belong to this conversation")

        file_id = UUID(session["file_id"])
        stored = await self._storage.finalize_upload(
            upload_id=upload_id,
            file_id=file_id,
            filename=session["filename"],
            content_type=session["content_type"],
            total_chunks=session["total_chunks"],
        )
        await self._redis.delete(self._upload_key(upload_id))

        attachment_type = self._attachment_type(
            session["content_type"],
            session["filename"],
        )
        return CompleteUploadResponse(
            file_id=stored.file_id,
            url=stored.public_url,
            filename=session["filename"],
            content_type=session["content_type"],
            attachment_type=attachment_type,
            size_bytes=session["size_bytes"],
            preview_url=stored.preview_url,
        )
