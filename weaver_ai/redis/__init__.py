"""Redis-based communication infrastructure for agents."""

from .connection_pool import (
    RedisPoolConfig,
    close_redis_pool,
    get_pool_stats,
    get_redis_pool,
    init_redis_pool,
)
from .mesh import RedisEventMesh
from .queue import WorkQueue
from .registry import RedisAgentRegistry

__all__ = [
    "RedisEventMesh",
    "WorkQueue",
    "RedisAgentRegistry",
    "RedisPoolConfig",
    "get_redis_pool",
    "init_redis_pool",
    "close_redis_pool",
    "get_pool_stats",
]
