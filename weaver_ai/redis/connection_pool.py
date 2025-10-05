"""Centralized Redis connection pool manager for optimal resource utilization.

This module provides a singleton connection pool that can be shared across all
components (registry, cache, event mesh, work queue) to avoid creating multiple
connections and maximize performance.

Performance Benefits:
- Single connection pool shared across all components
- Connection reuse eliminates TCP handshake overhead
- Configurable pool size and timeouts
- Health monitoring and automatic reconnection
- Connection statistics for monitoring

Example:
    >>> from weaver_ai.redis.connection_pool import get_redis_pool, RedisPoolConfig
    >>>
    >>> # Initialize with config
    >>> config = RedisPoolConfig(max_connections=100)
    >>> await init_redis_pool(config)
    >>>
    >>> # Get client from pool
    >>> redis_client = await get_redis_pool()
    >>> await redis_client.ping()
    >>>
    >>> # Close pool on shutdown
    >>> await close_redis_pool()
"""

from __future__ import annotations

import logging
import time
from typing import Any

import redis.asyncio as redis
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Global connection pool instance
_redis_pool: redis.Redis | None = None
_pool_stats: dict[str, Any] = {
    "total_connections_created": 0,
    "total_commands_executed": 0,
    "total_errors": 0,
    "pool_initialized_at": None,
    "last_health_check": None,
}


class RedisPoolConfig(BaseModel):
    """Configuration for Redis connection pool."""

    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=0, description="Redis database number")
    password: str | None = Field(default=None, description="Redis password")

    # Connection pool settings
    max_connections: int = Field(
        default=100,
        description="Maximum connections in pool (shared across all components)",
    )
    socket_timeout: float = Field(default=5.0, description="Socket timeout in seconds")
    socket_connect_timeout: float = Field(
        default=5.0, description="Socket connect timeout in seconds"
    )
    socket_keepalive: bool = Field(default=True, description="Enable TCP keepalive")
    socket_keepalive_options: dict[int, int] | None = Field(
        default=None, description="TCP keepalive options"
    )

    # Pool behavior
    health_check_interval: int = Field(
        default=30, description="Seconds between health checks"
    )
    retry_on_timeout: bool = Field(
        default=True, description="Retry commands on timeout"
    )
    decode_responses: bool = Field(
        default=False, description="Automatically decode responses to strings"
    )

    # Performance tuning
    max_idle_time: int = Field(
        default=300, description="Max seconds a connection can be idle"
    )
    retry_on_error: list[type[Exception]] | None = Field(
        default=None, description="Exception types to retry on"
    )


class RedisPoolError(Exception):
    """Base exception for Redis pool errors."""

    pass


class PoolNotInitializedError(RedisPoolError):
    """Pool has not been initialized."""

    pass


class PoolConnectionError(RedisPoolError):
    """Failed to connect to Redis."""

    pass


async def init_redis_pool(config: RedisPoolConfig) -> redis.Redis:
    """Initialize the global Redis connection pool.

    Args:
        config: Redis pool configuration

    Returns:
        Redis client connected to the pool

    Raises:
        PoolConnectionError: If connection fails
    """
    global _redis_pool, _pool_stats

    if _redis_pool is not None:
        logger.warning("Redis pool already initialized, returning existing pool")
        return _redis_pool

    try:
        # Build Redis URL
        redis_url = f"redis://{config.host}:{config.port}/{config.db}"

        # Create connection pool with optimized settings
        _redis_pool = await redis.from_url(
            redis_url,
            password=config.password,
            max_connections=config.max_connections,
            socket_timeout=config.socket_timeout,
            socket_connect_timeout=config.socket_connect_timeout,
            socket_keepalive=config.socket_keepalive,
            socket_keepalive_options=config.socket_keepalive_options,
            retry_on_timeout=config.retry_on_timeout,
            decode_responses=config.decode_responses,
            health_check_interval=config.health_check_interval,
        )

        # Test connection
        await _redis_pool.ping()

        # Update stats
        _pool_stats["pool_initialized_at"] = time.time()
        _pool_stats["last_health_check"] = time.time()
        _pool_stats["config"] = config.model_dump()

        logger.info(
            f"Redis connection pool initialized: {config.host}:{config.port} "
            f"(max_connections={config.max_connections})"
        )

        return _redis_pool

    except Exception as e:
        logger.error(f"Failed to initialize Redis pool: {e}", exc_info=True)
        _redis_pool = None
        raise PoolConnectionError(f"Failed to connect to Redis: {e}") from e


async def get_redis_pool() -> redis.Redis:
    """Get the global Redis connection pool.

    Returns:
        Redis client connected to the pool

    Raises:
        PoolNotInitializedError: If pool has not been initialized
    """
    if _redis_pool is None:
        raise PoolNotInitializedError(
            "Redis pool not initialized. Call init_redis_pool() first."
        )

    return _redis_pool


async def close_redis_pool() -> None:
    """Close the global Redis connection pool.

    This should be called during application shutdown to properly
    close all connections and free resources.
    """
    global _redis_pool

    if _redis_pool is None:
        logger.warning("Attempted to close uninitialized Redis pool")
        return

    try:
        await _redis_pool.aclose()
        logger.info("Redis connection pool closed successfully")

    except Exception as e:
        logger.error(f"Error closing Redis pool: {e}", exc_info=True)

    finally:
        _redis_pool = None


async def health_check() -> bool:
    """Check Redis connection pool health.

    Returns:
        True if healthy, False otherwise
    """
    global _pool_stats

    if _redis_pool is None:
        return False

    try:
        await _redis_pool.ping()
        _pool_stats["last_health_check"] = time.time()
        return True

    except Exception as e:
        logger.error(f"Redis pool health check failed: {e}")
        _pool_stats["total_errors"] += 1
        return False


def get_pool_stats() -> dict[str, Any]:
    """Get connection pool statistics.

    Returns:
        Dictionary with pool statistics and metrics
    """
    stats = _pool_stats.copy()

    if _redis_pool is not None:
        # Get pool info from connection pool
        pool = _redis_pool.connection_pool
        stats["pool_info"] = {
            "max_connections": pool.max_connections,
            "available_connections": len(pool._available_connections),
            "in_use_connections": len(pool._in_use_connections),
        }

        # Calculate uptime
        if stats.get("pool_initialized_at"):
            uptime_seconds = time.time() - stats["pool_initialized_at"]
            stats["uptime_seconds"] = round(uptime_seconds, 2)
            stats["uptime_hours"] = round(uptime_seconds / 3600, 2)

        # Time since last health check
        if stats.get("last_health_check"):
            seconds_since_check = time.time() - stats["last_health_check"]
            stats["seconds_since_last_health_check"] = round(seconds_since_check, 2)

    return stats


async def execute_command(command: str, *args, **kwargs) -> Any:
    """Execute a Redis command through the pool with stats tracking.

    Args:
        command: Redis command name
        *args: Command arguments
        **kwargs: Command keyword arguments

    Returns:
        Command result

    Raises:
        PoolNotInitializedError: If pool not initialized
    """
    global _pool_stats

    redis_client = await get_redis_pool()

    try:
        # Execute command
        cmd_func = getattr(redis_client, command)
        result = await cmd_func(*args, **kwargs)

        # Track stats
        _pool_stats["total_commands_executed"] += 1

        return result

    except Exception as e:
        _pool_stats["total_errors"] += 1
        logger.error(f"Redis command '{command}' failed: {e}")
        raise


# Context manager support
class RedisPoolContext:
    """Context manager for Redis pool lifecycle."""

    def __init__(self, config: RedisPoolConfig):
        self.config = config
        self.pool: redis.Redis | None = None

    async def __aenter__(self) -> redis.Redis:
        """Initialize pool on entry."""
        self.pool = await init_redis_pool(self.config)
        return self.pool

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close pool on exit."""
        await close_redis_pool()
