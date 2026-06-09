from uuid import UUID

from app.core.config import settings
from app.services.storage.base import ChunkTarget, StorageBackend, StoredFile


class S3StorageBackend(StorageBackend):
    def __init__(self) -> None:
        import boto3

        session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            region_name=settings.storage_region,
        )
        self._client = session.client("s3")
        self._bucket = settings.storage_bucket

    def _object_key(self, file_id: UUID, filename: str) -> str:
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
        key = self._object_key(file_id, filename)
        response = self._client.create_multipart_upload(
            Bucket=self._bucket,
            Key=key,
            ContentType=content_type,
        )
        upload_key = response["UploadId"]
        targets: list[ChunkTarget] = []
        for i in range(total_chunks):
            part_number = i + 1
            url = self._client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    "UploadId": upload_key,
                    "PartNumber": part_number,
                },
                ExpiresIn=settings.upload_signed_url_ttl_seconds,
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
        raise NotImplementedError("S3 chunks upload directly via pre-signed URLs")

    async def finalize_upload(
        self,
        *,
        upload_id: UUID,
        file_id: UUID,
        filename: str,
        content_type: str,
        total_chunks: int,
    ) -> StoredFile:
        key = self._object_key(file_id, filename)
        url = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=settings.upload_signed_url_ttl_seconds,
        )
        preview = url if content_type.startswith("image/") else None
        return StoredFile(
            file_id=file_id,
            storage_key=key,
            public_url=url,
            preview_url=preview,
        )

    async def read_file_bytes(self, storage_key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=storage_key)
        return response["Body"].read()
