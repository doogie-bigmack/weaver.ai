"""Redis-based nonce storage for replay attack prevention."""

from __future__ import annotations

import asyncio
import json
import logging
import time

import redis
import redis.asyncio as aioredis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RedisNonceStore:
    """
    Redis-backed nonce storage with TTL support for replay attack prevention.

    Features:
    - Atomic check-and-set operations
    - Automatic TTL-based expiration
    - Distributed across multiple servers
    - Resilient to Redis failures (with fallback to in-memory)
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        namespace: str = "nonce",
        ttl_seconds: int = 300,  # 5 minutes default
        fallback_to_memory: bool = True,
    ):
        """
        Initialize Redis nonce store.

        Args:
            redis_client: Redis async client instance
            namespace: Redis key namespace for nonces
            ttl_seconds: Time-to-live for nonces in seconds
            fallback_to_memory: If True, fallback to in-memory storage on Redis failure
        """
        self.redis = redis_client
        self.namespace = namespace
        self.ttl_seconds = ttl_seconds
        self.fallback_to_memory = fallback_to_memory

        # Fallback in-memory storage (used if Redis is unavailable)
        self._memory_store: dict[str, float] = {}
        self._memory_store_lock = asyncio.Lock()
        self._max_memory_nonces = 10000

        # Track Redis availability
        self._redis_available = True
        self._last_redis_check = 0
        self._redis_check_interval = 30  # Check Redis every 30 seconds

    def _make_key(self, nonce: str) -> str:
        """Create Redis key for nonce."""
        return f"{self.namespace}:{nonce}"

    async def _check_redis_health(self) -> bool:
        """Check if Redis is available."""
        current_time = time.time()

        # Don't check too frequently
        if current_time - self._last_redis_check < self._redis_check_interval:
            return self._redis_available

        self._last_redis_check = current_time

        try:
            await self.redis.ping()
            if not self._redis_available:
                logger.info("Redis connection restored for nonce storage")
            self._redis_available = True
            return True
        except (RedisError, ConnectionError, OSError) as e:
            if self._redis_available:
                logger.warning(f"Redis unavailable for nonce storage: {e}")
            self._redis_available = False
            return False

    async def _cleanup_memory_store(self) -> None:
        """Clean up expired nonces from memory store."""
        if not self._memory_store:
            return

        current_time = time.time()
        expired = [
            nonce
            for nonce, timestamp in self._memory_store.items()
            if current_time - timestamp > self.ttl_seconds
        ]

        for nonce in expired:
            del self._memory_store[nonce]

        # Enforce size limit (LRU eviction)
        if len(self._memory_store) > self._max_memory_nonces:
            # Sort by timestamp and remove oldest
            sorted_nonces = sorted(self._memory_store.items(), key=lambda x: x[1])
            for nonce, _ in sorted_nonces[
                : len(sorted_nonces) - self._max_memory_nonces
            ]:
                del self._memory_store[nonce]

    async def check_and_add(self, nonce: str) -> bool:
        """
        Atomically check if nonce exists and add it if not.

        Args:
            nonce: The nonce to check and add

        Returns:
            True if nonce was successfully added (not a replay)
            False if nonce already exists (replay detected)
        """
        # Try Redis first
        if await self._check_redis_health():
            try:
                key = self._make_key(nonce)

                # Use SET with NX (only set if not exists) and EX (expiration)
                # This is atomic - either sets with TTL or fails if exists
                result = await self.redis.set(
                    key,
                    json.dumps({"timestamp": time.time(), "ttl": self.ttl_seconds}),
                    nx=True,  # Only set if not exists
                    ex=self.ttl_seconds,  # Expire after TTL
                )

                # result is True if key was set, None if it already existed
                if result:
                    logger.debug(f"Nonce {nonce} added to Redis store")
                    return True
                else:
                    logger.warning(f"Nonce replay detected in Redis: {nonce}")
                    return False

            except (RedisError, ConnectionError, OSError) as e:
                logger.error(f"Redis error during nonce check: {e}")
                self._redis_available = False

                if not self.fallback_to_memory:
                    raise

        # Fallback to in-memory storage
        if self.fallback_to_memory:
            async with self._memory_store_lock:
                # Clean up expired entries
                await self._cleanup_memory_store()

                # Check if nonce exists
                if nonce in self._memory_store:
                    logger.warning(f"Nonce replay detected in memory: {nonce}")
                    return False

                # Add nonce with timestamp
                self._memory_store[nonce] = time.time()
                logger.debug(f"Nonce {nonce} added to memory store (Redis unavailable)")
                return True

        # If we get here, Redis is down and no fallback
        raise RedisError("Redis unavailable and fallback disabled")

    async def exists(self, nonce: str) -> bool:
        """
        Check if a nonce exists without adding it.

        Args:
            nonce: The nonce to check

        Returns:
            True if nonce exists, False otherwise
        """
        # Try Redis first
        if await self._check_redis_health():
            try:
                key = self._make_key(nonce)
                result = await self.redis.exists(key)
                return bool(result)
            except (RedisError, ConnectionError, OSError) as e:
                logger.error(f"Redis error during nonce existence check: {e}")
                self._redis_available = False

                if not self.fallback_to_memory:
                    raise

        # Fallback to in-memory storage
        if self.fallback_to_memory:
            async with self._memory_store_lock:
                await self._cleanup_memory_store()
                return nonce in self._memory_store

        raise RedisError("Redis unavailable and fallback disabled")

    async def cleanup_expired(self) -> int:
        """
        Manually trigger cleanup of expired nonces.

        Returns:
            Number of expired nonces cleaned up
        """
        cleaned = 0

        # Redis handles expiration automatically via TTL
        # This method is mainly for the in-memory fallback

        if self.fallback_to_memory and self._memory_store:
            async with self._memory_store_lock:
                initial_size = len(self._memory_store)
                await self._cleanup_memory_store()
                cleaned = initial_size - len(self._memory_store)

                if cleaned > 0:
                    logger.info(f"Cleaned {cleaned} expired nonces from memory store")

        return cleaned

    async def get_stats(self) -> dict:
        """
        Get statistics about the nonce store.

        Returns:
            Dictionary with store statistics
        """
        stats = {
            "redis_available": self._redis_available,
            "ttl_seconds": self.ttl_seconds,
            "memory_store_size": (
                len(self._memory_store) if self.fallback_to_memory else 0
            ),
            "namespace": self.namespace,
        }

        # Try to get Redis stats
        if await self._check_redis_health():
            try:
                # Count nonces in Redis (scan with pattern)
                pattern = f"{self.namespace}:*"
                cursor = 0
                redis_count = 0

                # Use SCAN to avoid blocking on large datasets
                while True:
                    cursor, keys = await self.redis.scan(
                        cursor, match=pattern, count=100
                    )
                    redis_count += len(keys)
                    if cursor == 0:
                        break

                stats["redis_nonce_count"] = redis_count

            except (RedisError, ConnectionError, OSError) as e:
                logger.error(f"Failed to get Redis stats: {e}")
                stats["redis_nonce_count"] = "unavailable"

        return stats


class SyncRedisNonceStore:
    """
    Synchronous wrapper for RedisNonceStore for use in sync contexts.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        namespace: str = "nonce",
        ttl_seconds: int = 300,
        fallback_to_memory: bool = True,
    ):
        """
        Initialize synchronous Redis nonce store.

        Args:
            redis_url: Redis connection URL
            namespace: Redis key namespace for nonces
            ttl_seconds: Time-to-live for nonces in seconds
            fallback_to_memory: If True, fallback to in-memory storage on Redis failure
        """
        self.redis_url = redis_url
        self.namespace = namespace
        self.ttl_seconds = ttl_seconds
        self.fallback_to_memory = fallback_to_memory

        # In-memory fallback for sync context
        self._memory_store: dict[str, float] = {}
        self._max_memory_nonces = 10000

        # Sync Redis client
        self._redis_client: redis.Redis | None = None
        self._redis_available = True

    def _get_redis(self) -> redis.Redis:
        """Get or create synchronous Redis client."""
        if self._redis_client is None:
            # Use synchronous Redis client, not async
            self._redis_client = redis.Redis.from_url(
                self.redis_url, decode_responses=True
            )
        return self._redis_client

    def _cleanup_memory_store(self) -> None:
        """Clean up expired nonces from memory store."""
        if not self._memory_store:
            return

        current_time = time.time()
        expired = [
            nonce
            for nonce, timestamp in self._memory_store.items()
            if current_time - timestamp > self.ttl_seconds
        ]

        for nonce in expired:
            del self._memory_store[nonce]

        # Enforce size limit
        if len(self._memory_store) > self._max_memory_nonces:
            sorted_nonces = sorted(self._memory_store.items(), key=lambda x: x[1])
            for nonce, _ in sorted_nonces[
                : len(sorted_nonces) - self._max_memory_nonces
            ]:
                del self._memory_store[nonce]

    def check_and_add(self, nonce: str) -> bool:
        """
        Synchronously check if nonce exists and add it if not.

        Args:
            nonce: The nonce to check and add

        Returns:
            True if nonce was successfully added (not a replay)
            False if nonce already exists (replay detected)
        """
        # Run async version in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop in current thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # If we're already in an async context, we can't use run_until_complete
        # Fall back to sync implementation
        try:
            redis_client = self._get_redis()
            key = f"{self.namespace}:{nonce}"

            # Sync version of atomic set with NX
            result = redis_client.set(
                key,
                json.dumps({"timestamp": time.time(), "ttl": self.ttl_seconds}),
                nx=True,
                ex=self.ttl_seconds,
            )

            if result:
                logger.debug(f"Nonce {nonce} added to Redis store (sync)")
                return True
            else:
                logger.warning(f"Nonce replay detected in Redis (sync): {nonce}")
                return False

        except (RedisError, ConnectionError, OSError) as e:
            logger.error(f"Redis error during sync nonce check: {e}")

            if self.fallback_to_memory:
                # Fallback to in-memory
                self._cleanup_memory_store()

                if nonce in self._memory_store:
                    logger.warning(f"Nonce replay detected in memory (sync): {nonce}")
                    return False

                # Add nonce with timestamp
                self._memory_store[nonce] = time.time()

                # Enforce size limit after adding (to match async behavior)
                if len(self._memory_store) > self._max_memory_nonces:
                    sorted_nonces = sorted(
                        self._memory_store.items(), key=lambda x: x[1]
                    )
                    for old_nonce, _ in sorted_nonces[
                        : len(sorted_nonces) - self._max_memory_nonces
                    ]:
                        del self._memory_store[old_nonce]

                logger.debug(
                    f"Nonce {nonce} added to memory store (sync, Redis unavailable)"
                )
                return True

            raise

    def close(self) -> None:
        """Close Redis connection."""
        if self._redis_client:
            self._redis_client.close()
            self._redis_client = None
