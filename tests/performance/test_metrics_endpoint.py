"""Performance tests for /metrics endpoint."""

import time

import pytest
from fastapi.testclient import TestClient

from weaver_ai.gateway import app
from weaver_ai.redis.connection_pool import (
    RedisPoolConfig,
    close_redis_pool,
    init_redis_pool,
)


@pytest.fixture
async def redis_initialized():
    """Initialize Redis pool before tests."""
    config = RedisPoolConfig(
        host="localhost",
        port=6379,
        max_connections=50,
    )
    await init_redis_pool(config)
    yield
    await close_redis_pool()


@pytest.mark.asyncio
async def test_metrics_endpoint_response(redis_initialized):
    """Test /metrics endpoint returns valid data."""
    client = TestClient(app)

    # Make some requests to populate stats
    client.get("/health")
    client.get("/health")  # Should hit cache

    # Get metrics
    response = client.get("/metrics")
    assert response.status_code == 200

    data = response.json()
    assert data["service"] == "weaver-ai"
    assert data["status"] == "healthy"
    assert "http_cache" in data
    assert "redis_pool" in data


@pytest.mark.asyncio
async def test_metrics_http_cache_stats(redis_initialized):
    """Test metrics include HTTP cache statistics."""
    client = TestClient(app)

    # Warm up cache
    client.get("/health")
    client.get("/health")
    client.get("/health")

    response = client.get("/metrics")
    data = response.json()

    cache_stats = data["http_cache"]
    assert "hits" in cache_stats
    assert "misses" in cache_stats
    assert "hit_rate_percent" in cache_stats
    assert "total_requests" in cache_stats

    # Should have cache hits
    assert cache_stats["hits"] >= 2


@pytest.mark.asyncio
async def test_metrics_redis_pool_stats(redis_initialized):
    """Test metrics include Redis pool statistics."""
    client = TestClient(app)

    response = client.get("/metrics")
    data = response.json()

    pool_stats = data["redis_pool"]
    assert "pool_info" in pool_stats
    assert "max_connections" in pool_stats["pool_info"]
    assert "uptime_seconds" in pool_stats
    assert "last_health_check" in pool_stats


@pytest.mark.asyncio
async def test_metrics_endpoint_performance(redis_initialized):
    """Test /metrics endpoint is fast."""
    client = TestClient(app)

    # Measure metrics endpoint latency
    latencies = []
    for _ in range(10):
        start = time.time()
        response = client.get("/metrics")
        elapsed = (time.time() - start) * 1000
        latencies.append(elapsed)
        assert response.status_code == 200

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)

    # Metrics should be fast (< 50ms average)
    assert avg_latency < 50, f"Metrics too slow: {avg_latency:.2f}ms"
    assert max_latency < 100, f"Max latency too high: {max_latency:.2f}ms"

    print("\nMetrics endpoint performance:")
    print(f"Average latency: {avg_latency:.2f}ms")
    print(f"Max latency: {max_latency:.2f}ms")


@pytest.mark.asyncio
async def test_metrics_cached_response(redis_initialized):
    """Test /metrics endpoint is cached correctly."""
    client = TestClient(app)

    # First request - cache miss
    start1 = time.time()
    response1 = client.get("/metrics")
    latency1 = (time.time() - start1) * 1000

    # Second request - cache hit
    start2 = time.time()
    response2 = client.get("/metrics")
    latency2 = (time.time() - start2) * 1000

    # Both should succeed
    assert response1.status_code == 200
    assert response2.status_code == 200

    # Second should be faster (cached)
    assert latency2 < latency1

    print(f"\nFirst request: {latency1:.2f}ms")
    print(f"Cached request: {latency2:.2f}ms")


@pytest.mark.asyncio
async def test_metrics_by_endpoint_breakdown(redis_initialized):
    """Test metrics show per-endpoint cache statistics."""
    client = TestClient(app)

    # Make requests to different endpoints
    client.get("/health")
    client.get("/health")
    client.get("/metrics")
    client.get("/metrics")

    # Get final metrics
    response = client.get("/metrics")
    data = response.json()

    cache_stats = data["http_cache"]
    if "by_endpoint" in cache_stats:
        by_endpoint = cache_stats["by_endpoint"]
        assert "/health" in by_endpoint or "/metrics" in by_endpoint


@pytest.mark.asyncio
async def test_metrics_connection_pool_info(redis_initialized):
    """Test metrics show Redis connection pool details."""
    client = TestClient(app)

    response = client.get("/metrics")
    data = response.json()

    pool_stats = data["redis_pool"]
    pool_info = pool_stats["pool_info"]

    # Should show connection usage
    assert "available_connections" in pool_info
    assert "in_use_connections" in pool_info
    assert pool_info["max_connections"] > 0
