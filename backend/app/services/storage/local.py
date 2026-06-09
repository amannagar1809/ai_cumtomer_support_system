import hashlib
import hmac
import shutil
import time
from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.services.storage.base import ChunkTarget, StorageBackend, StoredFile


class LocalStorageBackend(StorageBackend):
    def __init__(self) -> None:
        self._root = Path(settings.upload_local_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        self._chunks_root = self._root / "chunks"
        self._files_root = self._root / "files"
        self._chunks_root.mkdir(parents=True, exist_ok=True)
        self._files_root.mkdir(parents=True, exist_ok=True)

    def _chunk_path(self, upload_id: UUID, chunk_index: int) -> Path:
        return self._chunks_root / str(upload_id) / f"{chunk_index}.part"

    def _sign(self, file_id: UUID, expires: int) -> str:
        payload = f"{file_id}:{expires}"
        digest = hmac.new(
            settings.upload_signing_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return digest

    def signed_file_url(self, file_id: UUID) -> str:
        expires = int(time.time()) + settings.upload_signed_url_ttl_seconds
        token = self._sign(file_id, expires)
        return (
            f"/api/v1/chat/uploads/files/{file_id}"
            f"?expires={expires}&token={token}"
        )

    def verify_signed_url(self, file_id: UUID, expires: int, token: str) -> bool:
        if expires < int(time.time()):
            return False
        expected = self._sign(file_id, expires)
        return hmac.compare_digest(expected, token)

    async def create_chunk_targets(
        self,
        *,
        upload_id: UUID,
        file_id: UUID,
        filename: str,
        content_type: str,
        total_chunks: int,
    ) -> list[ChunkTarget]:
        chunk_dir = self._chunks_root / str(upload_id)
        chunk_dir.mkdir(parents=True, exist_ok=True)
        return [
            ChunkTarget(
                chunk_index=i,
                upload_url=f"/api/v1/chat/uploads/{upload_id}/chunks/{i}",
                method="PUT",
            )
            for i in range(total_chunks)
        ]

    async def store_chunk(
        self,
        *,
        upload_id: UUID,
        chunk_index: int,
        data: bytes,
    ) -> None:
        path = self._chunk_path(upload_id, chunk_index)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def finalize_upload(
        self,
        *,
        upload_id: UUID,
        file_id: UUID,
        filename: str,
        content_type: str,
        total_chunks: int,
    ) -> StoredFile:
        dest = self._files_root / str(file_id)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as out:
            for i in range(total_chunks):
                chunk = self._chunk_path(upload_id, i)
                if not chunk.exists():
                    raise FileNotFoundError(f"Missing chunk {i} for upload {upload_id}")
                out.write(chunk.read_bytes())

        chunk_dir = self._chunks_root / str(upload_id)
        if chunk_dir.exists():
            shutil.rmtree(chunk_dir, ignore_errors=True)

        url = self.signed_file_url(file_id)
        preview = url if content_type.startswith("image/") else None
        return StoredFile(
            file_id=file_id,
            storage_key=str(dest),
            public_url=url,
            preview_url=preview,
        )

    async def read_file_bytes(self, storage_key: str) -> bytes:
        return Path(storage_key).read_bytes()
