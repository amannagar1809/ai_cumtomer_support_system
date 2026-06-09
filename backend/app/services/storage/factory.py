from functools import lru_cache

from app.core.config import settings
from app.services.storage.base import StorageBackend
from app.services.storage.gcs import GCSStorageBackend
from app.services.storage.local import LocalStorageBackend
from app.services.storage.s3 import S3StorageBackend


@lru_cache
def get_storage_backend() -> StorageBackend:
    provider = settings.storage_provider.lower()
    if provider == "s3":
        return S3StorageBackend()
    if provider == "gcs":
        return GCSStorageBackend()
    return LocalStorageBackend()
