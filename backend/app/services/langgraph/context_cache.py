"""Context caching service for Redis-based context caching with compression."""

import json
import logging
import zlib
from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_TTL_SECONDS = 300  # 5 minutes
CACHE_KEY_PREFIX = "context:"
COMPRESSION_THRESHOLD = 1024  # Compress if larger than 1KB
COMPRESSION_LEVEL = 6  # zlib compression level (0-9, 6 is default)


class CacheStats(BaseModel):
    """Cache statistics for monitoring."""

    hits: int = Field(default=0, description="Cache hits")
    misses: int = Field(default=0, description="Cache misses")
    sets: int = Field(default=0, description="Cache sets")
    invalidations: int = Field(default=0, description="Cache invalidations")
    compressions: int = Field(default=0, description="Number of compressions")
    decompressions: int = Field(default=0, description="Number of decompressions")


class ContextCacheService:
    """Redis-based context caching service with compression and cache-aside pattern."""

    def __init__(
        self,
        ttl_seconds: int = CACHE_TTL_SECONDS,
        compression_threshold: int = COMPRESSION_THRESHOLD,
        compression_level: int = COMPRESSION_LEVEL,
    ):
        """
        Initialize the context cache service.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds
            compression_threshold: Size threshold for compression in bytes
            compression_level: zlib compression level (0-9)
        """
        self.ttl_seconds = ttl_seconds
        self.compression_threshold = compression_threshold
        self.compression_level = compression_level
        self._redis = get_redis_client()
        self.stats = CacheStats()

    def _generate_cache_key(
        self,
        user_id: str,
        context_type: str = "customer",
    ) -> str:
        """
        Generate a cache key for the context.

        Args:
            user_id: The user ID
            context_type: Type of context (customer, conversation, etc.)

        Returns:
            Cache key string
        """
        return f"{CACHE_KEY_PREFIX}{context_type}:{user_id}"

    def _compress_data(self, data: str) -> tuple[bytes, bool]:
        """
        Compress data if it exceeds threshold.

        Args:
            data: String data to compress

        Returns:
            Tuple of (compressed data, whether compression was applied)
        """
        data_bytes = data.encode("utf-8")

        if len(data_bytes) < self.compression_threshold:
            return data_bytes, False

        compressed = zlib.compress(data_bytes, level=self.compression_level)
        self.stats.compressions += 1
        logger.debug(f"Compressed data: {len(data_bytes)} -> {len(compressed)} bytes")
        return compressed, True

    def _decompress_data(self, data: bytes, is_compressed: bool) -> str:
        """
        Decompress data if it was compressed.

        Args:
            data: Data to decompress
            is_compressed: Whether data was compressed

        Returns:
            Decompressed string
        """
        if not is_compressed:
            return data.decode("utf-8")

        decompressed = zlib.decompress(data)
        self.stats.decompressions += 1
        return decompressed.decode("utf-8")

    async def get(
        self,
        user_id: str,
        context_type: str = "customer",
    ) -> Optional[dict[str, Any]]:
        """
        Get context from cache (cache-aside pattern).

        Args:
            user_id: The user ID
            context_type: Type of context

        Returns:
            Cached context data or None if not found
        """
        cache_key = self._generate_cache_key(user_id, context_type)

        try:
            cached_data = await self._redis.get(cache_key)

            if cached_data is None:
                self.stats.misses += 1
                logger.debug(f"Cache miss for key: {cache_key}")
                return None

            # Check if data is compressed (first byte indicates compression)
            is_compressed = cached_data[0] == 1
            if is_compressed:
                # Remove compression flag byte
                cached_data = cached_data[1:]

            decompressed = self._decompress_data(cached_data, is_compressed)
            context_data = json.loads(decompressed)

            self.stats.hits += 1
            logger.debug(f"Cache hit for key: {cache_key}")
            return context_data

        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            self.stats.misses += 1
            return None

    async def set(
        self,
        user_id: str,
        context_data: dict[str, Any],
        context_type: str = "customer",
    ) -> bool:
        """
        Set context in cache with TTL.

        Args:
            user_id: The user ID
            context_data: Context data to cache
            context_type: Type of context

        Returns:
            True if successful, False otherwise
        """
        cache_key = self._generate_cache_key(user_id, context_type)

        try:
            # Serialize to JSON
            json_data = json.dumps(context_data)

            # Compress if needed
            compressed_data, is_compressed = self._compress_data(json_data)

            # Add compression flag byte
            if is_compressed:
                compressed_data = b"\x01" + compressed_data
            else:
                compressed_data = b"\x00" + compressed_data

            # Set in Redis with TTL
            await self._redis.setex(cache_key, self.ttl_seconds, compressed_data)

            self.stats.sets += 1
            logger.debug(f"Cache set for key: {cache_key} (TTL: {self.ttl_seconds}s)")
            return True

        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False

    async def invalidate(
        self,
        user_id: str,
        context_type: str = "customer",
    ) -> bool:
        """
        Invalidate cache entry for a user.

        Args:
            user_id: The user ID
            context_type: Type of context

        Returns:
            True if successful, False otherwise
        """
        cache_key = self._generate_cache_key(user_id, context_type)

        try:
            await self._redis.delete(cache_key)
            self.stats.invalidations += 1
            logger.info(f"Cache invalidated for key: {cache_key}")
            return True

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return False

    async def invalidate_all_for_user(self, user_id: str) -> bool:
        """
        Invalidate all cache entries for a user.

        Args:
            user_id: The user ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get all keys for this user
            pattern = f"{CACHE_KEY_PREFIX}*:{user_id}"
            keys = await self._redis.keys(pattern)

            if keys:
                await self._redis.delete(*keys)
                self.stats.invalidations += len(keys)
                logger.info(f"Invalidated {len(keys)} cache entries for user: {user_id}")

            return True

        except Exception as e:
            logger.error(f"Error invalidating all cache entries: {e}")
            return False

    async def preload_context(
        self,
        user_id: str,
        context_type: str = "customer",
        context_loader: Any = None,
    ) -> Optional[dict[str, Any]]:
        """
        Preload context into cache (called when user starts typing).

        Args:
            user_id: The user ID
            context_type: Type of context
            context_loader: Async function to load context from DB

        Returns:
            Loaded context data or None
        """
        # First check if already cached
        cached = await self.get(user_id, context_type)
        if cached:
            logger.debug(f"Context already cached for user: {user_id}")
            return cached

        # Load from DB if not cached
        if context_loader:
            try:
                context_data = await context_loader(user_id)
                if context_data:
                    await self.set(user_id, context_data, context_type)
                    logger.info(f"Preloaded context for user: {user_id}")
                    return context_data
            except Exception as e:
                logger.error(f"Error preloading context: {e}")

        return None

    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            Cache statistics
        """
        return self.stats

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self.stats = CacheStats()
        logger.info("Cache statistics reset")

    async def get_cache_size(self) -> int:
        """
        Get approximate cache size (number of keys).

        Returns:
            Number of cache keys
        """
        try:
            pattern = f"{CACHE_KEY_PREFIX}*"
            keys = await self._redis.keys(pattern)
            return len(keys)
        except Exception as e:
            logger.error(f"Error getting cache size: {e}")
            return 0

    async def clear_all_cache(self) -> bool:
        """
        Clear all context cache entries.

        Returns:
            True if successful, False otherwise
        """
        try:
            pattern = f"{CACHE_KEY_PREFIX}*"
            keys = await self._redis.keys(pattern)

            if keys:
                await self._redis.delete(*keys)
                logger.info(f"Cleared {len(keys)} cache entries")

            return True

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
