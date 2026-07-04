from datetime import timedelta
from uuid import UUID

from app.core.config import settings
from app.services.storage.base import ChunkTarget, StorageBackend, StoredFile


class GCSStorageBackend(StorageBackend):
    def __init__(self) -> None:
        from google.cloud import storage

        if settings.gcs_credentials_path:
            self._client = storage.Client.from_service_account_json(
                settings.gcs_credentials_path
            )
        else:
            self._client = storage.Client()
        self._bucket = self._client.bucket(settings.storage_bucket)

    def _object_name(self, file_id: UUID, filename: str) -> str:
        return f"chat-uploads/{file_id}/{filename}"

    async def create_chunk_targets(
        self,
        *,
        upload_id: UUID,
        file_id: UUID,
        filename: str,
        content_type: str,
        total_chunks: int,
    ) -> list[ChunkTarget]:
        blob = self._bucket.blob(self._object_name(file_id, filename))
        targets: list[ChunkTarget] = []
        for i in range(total_chunks):
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=settings.upload_signed_url_ttl_seconds),
                method="PUT",
                content_type=content_type,
            )
            targets.append(ChunkTarget(chunk_index=i, upload_url=url, method="PUT"))
        return targets

    async def store_chunk(
        self,
        *,
        upload_id: UUID,
        chunk_index: int,
        data: bytes,
    ) -> None:
        raise NotImplementedError("GCS chunks upload directly via pre-signed URLs")

    async def finalize_upload(
        self,
        *,
        upload_id: UUID,
        file_id: UUID,
        filename: str,
        content_type: str,
        total_chunks: int,
    ) -> StoredFile:
        name = self._object_name(file_id, filename)
        blob = self._bucket.blob(name)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=settings.upload_signed_url_ttl_seconds),
            method="GET",
        )
        preview = url if content_type.startswith("image/") else None
        return StoredFile(
            file_id=file_id,
            storage_key=name,
            public_url=url,
            preview_url=preview,
        )

    async def read_file_bytes(self, storage_key: str) -> bytes:
        blob = self._bucket.blob(storage_key)
        return blob.download_as_bytes()
