from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass
class ChunkTarget:
    chunk_index: int
    upload_url: str
    method: str = "PUT"


@dataclass
class StoredFile:
    file_id: UUID
    storage_key: str
    public_url: str
    preview_url: str | None


class StorageBackend(ABC):
    @abstractmethod
    async def create_chunk_targets(
        self,
        *,
        upload_id: UUID,
        file_id: UUID,
        filename: str,
        content_type: str,
        total_chunks: int,
    ) -> list[ChunkTarget]:
        pass

    @abstractmethod
    async def store_chunk(
        self,
        *,
        upload_id: UUID,
        chunk_index: int,
        data: bytes,
    ) -> None:
        pass

    @abstractmethod
    async def finalize_upload(
        self,
        *,
        upload_id: UUID,
        file_id: UUID,
        filename: str,
        content_type: str,
        total_chunks: int,
    ) -> StoredFile:
        pass

    @abstractmethod
    async def read_file_bytes(self, storage_key: str) -> bytes:
        pass
