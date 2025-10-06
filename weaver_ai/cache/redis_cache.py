"""Redis caching for model responses with intelligent TTL strategies."""

from __future__ import annotations

import hashlib
import json
import logging
import time

import redis.asyncio as redis  # type: ignore[import-untyped]
from pydantic import BaseModel

from weaver_ai.redis.connection_pool import get_redis_pool

logger = logging.getLogger(__name__)


class CacheConfig(BaseModel):
    """Configuration for Redis cache."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    max_connections: int = 50
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0

    # TTL strategies (in seconds)
    ttl_static: int = 3600  # 1 hour for static queries
    ttl_dynamic: int = 300  # 5 minutes for dynamic queries
    ttl_calculation: int = 86400  # 24 hours for calculation results
    ttl_default: int = 600  # 10 minutes default

    # Cache behavior
    enabled: bool = True
    prefix: str = "weaver:"
    track_stats: bool = True


class RedisCache:
    """Redis cache implementation with intelligent TTL and key generation.

    Uses the shared Redis connection pool for optimal performance.
    """

    def __init__(self, config: CacheConfig):
        self.config = config
        self.client: redis.Redis | None = None
        self._connected = False

        # Cache statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "total_latency_saved_ms": 0.0,
        }

    async def connect(self) -> bool:
        """Connect to Redis server using shared connection pool."""
        if self._connected:
            return True

        try:
            # Use shared connection pool instead of creating new connections
            self.client = await get_redis_pool()
            self._connected = True
            logger.info("Connected to shared Redis connection pool")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Redis pool: {e}")
            self.client = None
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from Redis (no-op for shared pool).

        The shared pool is managed by the application lifecycle,
        so we don't close it here.
        """
        self._connected = False
        self.client = None
        logger.info("Disconnected from Redis pool")

    def _generate_key(self, query: str, model: str, **kwargs) -> str:
        """Generate cache key based on query and parameters."""
        # Create a deterministic key from query and parameters
        key_parts = [query, model, json.dumps(kwargs, sort_keys=True)]

        key_str = "|".join(key_parts)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()

        return f"{self.config.prefix}{model}:{key_hash}"

    def _determine_ttl(self, query: str) -> int:
        """Determine TTL based on query type."""
        query_lower = query.lower()

        # Static queries (definitions, explanations)
        if any(
            word in query_lower for word in ["what is", "define", "explain", "how does"]
        ):
            return self.config.ttl_static

        # Calculation queries (math, conversions)
        if any(char in query for char in ["+", "-", "*", "/", "="]) or any(
            word in query_lower for word in ["calculate", "compute", "convert"]
        ):
            return self.config.ttl_calculation

        # Dynamic queries (current, latest, today)
        if any(
            word in query_lower
            for word in ["current", "latest", "today", "now", "recent"]
        ):
            return self.config.ttl_dynamic

        return self.config.ttl_default

    async def get(self, query: str, model: str, **kwargs) -> dict | None:
        """Get cached response if available."""
        if not self.config.enabled or not self._connected:
            return None

        key = self._generate_key(query, model, **kwargs)

        try:
            if self.client is None:
                return None

            start_time = time.time()
            data = await self.client.get(key)

            if data:
                result = json.loads(data)
                elapsed_ms = (time.time() - start_time) * 1000

                if self.config.track_stats:
                    self.stats["hits"] += 1
                    # Estimate saved latency (assuming cache saves 100-500ms)
                    self.stats["total_latency_saved_ms"] += 200 - elapsed_ms

                logger.debug(
                    f"Cache hit for key: {key[:20]}... (latency: {elapsed_ms:.2f}ms)"
                )
                return result  # type: ignore[no-any-return]

            if self.config.track_stats:
                self.stats["misses"] += 1

            logger.debug(f"Cache miss for key: {key[:20]}...")
            return None

        except Exception as e:
            if self.config.track_stats:
                self.stats["errors"] += 1
            logger.error(f"Cache get error: {e}")
            return None

    async def set(self, query: str, model: str, response: dict, **kwargs) -> bool:
        """Cache a model response."""
        if not self.config.enabled or not self._connected:
            return False

        key = self._generate_key(query, model, **kwargs)
        ttl = self._determine_ttl(query)

        try:
            if self.client is None:
                return False

            data = json.dumps(response)
            await self.client.setex(key, ttl, data)
            logger.debug(f"Cached response for key: {key[:20]}... (TTL: {ttl}s)")
            return True

        except Exception as e:
            if self.config.track_stats:
                self.stats["errors"] += 1
            logger.error(f"Cache set error: {e}")
            return False

    async def invalidate(self, pattern: str | None = None) -> int:
        """Invalidate cache entries matching pattern."""
        if not self._connected:
            return 0

        try:
            if pattern:
                search_pattern = f"{self.config.prefix}{pattern}"
            else:
                search_pattern = f"{self.config.prefix}*"

            if self.client is None:
                return 0

            keys = []
            async for key in self.client.scan_iter(match=search_pattern):
                keys.append(key)

            if keys:
                await self.client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries")

            return len(keys)

        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self.config.track_stats:
            return {}

        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (
            (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        )

        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "errors": self.stats["errors"],
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total_requests,
            "latency_saved_ms": f"{self.stats['total_latency_saved_ms']:.2f}",
            "avg_latency_saved_ms": (
                f"{self.stats['total_latency_saved_ms'] / self.stats['hits']:.2f}"
                if self.stats["hits"] > 0
                else "0.00"
            ),
        }

    async def clear_stats(self) -> None:
        """Clear cache statistics."""
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "total_latency_saved_ms": 0.0,
        }
