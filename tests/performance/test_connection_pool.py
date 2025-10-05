"""Performance tests for Redis connection pool."""

import asyncio
import time

import pytest

from weaver_ai.redis.connection_pool import (
    PoolNotInitializedError,
    RedisPoolConfig,
    close_redis_pool,
    get_pool_stats,
    get_redis_pool,
    init_redis_pool,
)


@pytest.fixture
async def redis_pool():
    """Initialize Redis pool for tests."""
    config = RedisPoolConfig(
        host="localhost",
        port=6379,
        max_connections=50,
    )
    pool = await init_redis_pool(config)
    yield pool
    await close_redis_pool()


@pytest.mark.asyncio
async def test_pool_initialization():
    """Test Redis pool initializes correctly."""
    config = RedisPoolConfig(
        host="localhost",
        port=6379,
        max_connections=50,
    )

    pool = await init_redis_pool(config)
    assert pool is not None

    # Test connection works
    await pool.ping()

    # Get pool stats
    stats = get_pool_stats()
    assert stats["pool_initialized_at"] is not None
    assert stats["config"]["max_connections"] == 50

    await close_redis_pool()


@pytest.mark.asyncio
async def test_pool_reuse():
    """Test connection pool reuses connections efficiently."""
    config = RedisPoolConfig(max_connections=20)
    await init_redis_pool(config)

    start_time = time.time()

    # Execute multiple commands sequentially to test connection reuse
    pool = await get_redis_pool()
    for i in range(100):
        await pool.set(f"test_key_{i}", f"value_{i}")
        value = await pool.get(f"test_key_{i}")
        assert value.decode() == f"value_{i}"

    elapsed = time.time() - start_time

    # With connection pooling, this should be fast (< 2 seconds)
    assert elapsed < 2.0, f"Pool reuse too slow: {elapsed:.2f}s"

    # Cleanup
    for i in range(100):
        await pool.delete(f"test_key_{i}")

    await close_redis_pool()


@pytest.mark.asyncio
async def test_pool_stats_tracking():
    """Test pool statistics are tracked correctly."""
    config = RedisPoolConfig(max_connections=20)
    await init_redis_pool(config)

    # Execute some commands
    pool = await get_redis_pool()
    await pool.ping()
    await pool.set("test", "value")
    await pool.get("test")

    # Get stats
    stats = get_pool_stats()
    assert "pool_info" in stats
    assert "max_connections" in stats["pool_info"]
    assert stats["pool_info"]["max_connections"] == 20
    assert "uptime_seconds" in stats

    # Cleanup
    await pool.delete("test")
    await close_redis_pool()


@pytest.mark.asyncio
async def test_pool_not_initialized_error():
    """Test error when accessing pool before initialization."""
    # Ensure pool is closed
    await close_redis_pool()

    with pytest.raises(PoolNotInitializedError):
        await get_redis_pool()


@pytest.mark.asyncio
async def test_concurrent_access_performance(redis_pool):
    """Test pool handles concurrent access efficiently."""
    num_concurrent = 50
    num_operations = 10

    async def concurrent_operations(worker_id: int):
        pool = await get_redis_pool()
        for i in range(num_operations):
            key = f"worker_{worker_id}_op_{i}"
            await pool.set(key, f"value_{i}")
            value = await pool.get(key)
            assert value.decode() == f"value_{i}"
            await pool.delete(key)

    start_time = time.time()

    # Run concurrent workers
    tasks = [concurrent_operations(i) for i in range(num_concurrent)]
    await asyncio.gather(*tasks)

    elapsed = time.time() - start_time
    total_ops = num_concurrent * num_operations * 3  # set, get, delete

    ops_per_second = total_ops / elapsed

    # Should achieve at least 1000 ops/second with connection pooling
    assert ops_per_second > 1000, f"Only {ops_per_second:.0f} ops/sec"

    print(f"\nConcurrent performance: {ops_per_second:.0f} ops/sec")


@pytest.mark.asyncio
async def test_pool_health_check(redis_pool):
    """Test pool health check functionality."""
    from weaver_ai.redis.connection_pool import health_check

    # Initial health check
    is_healthy = await health_check()
    assert is_healthy

    # Check stats updated
    stats = get_pool_stats()
    assert stats["last_health_check"] is not None


@pytest.mark.asyncio
async def test_connection_limit_enforcement():
    """Test pool enforces max connection limit."""
    config = RedisPoolConfig(max_connections=5)
    await init_redis_pool(config)

    pool = await get_redis_pool()

    # Try to use more than max connections
    async def hold_connection():
        await pool.ping()
        await asyncio.sleep(0.1)

    # Should handle gracefully within timeout
    start_time = time.time()
    tasks = [hold_connection() for _ in range(10)]
    await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    # Should complete without hanging
    assert elapsed < 5.0

    await close_redis_pool()


@pytest.mark.asyncio
async def test_pool_context_manager():
    """Test pool context manager lifecycle."""
    from weaver_ai.redis.connection_pool import RedisPoolContext

    config = RedisPoolConfig(max_connections=10)

    async with RedisPoolContext(config) as pool:
        # Pool should be initialized
        await pool.ping()

        # Should be able to get pool
        same_pool = await get_redis_pool()
        assert same_pool is pool

    # Pool should be closed after context exit
    with pytest.raises(PoolNotInitializedError):
        await get_redis_pool()
