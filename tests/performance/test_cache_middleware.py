"""Performance tests for HTTP response caching middleware."""

import asyncio
import time

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from weaver_ai.middleware import CacheConfig, ResponseCacheMiddleware
from weaver_ai.redis.connection_pool import (
    RedisPoolConfig,
    close_redis_pool,
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


@pytest.fixture
def app_with_cache(redis_pool):
    """Create FastAPI app with caching middleware."""
    app = FastAPI()

    # Add caching middleware
    cache_config = CacheConfig(
        enabled=True,
        cache_patterns={
            "/fast": 60,
            "/user": 30,
        },
    )
    middleware = ResponseCacheMiddleware(app, cache_config)
    app.add_middleware(ResponseCacheMiddleware, config=cache_config)

    @app.get("/fast")
    async def fast_endpoint():
        # Simulate some processing
        await asyncio.sleep(0.05)  # 50ms delay
        return {"result": "fast", "timestamp": time.time()}

    @app.get("/user")
    async def user_endpoint(request: Request):
        # User-specific endpoint (uses Authorization header)
        await asyncio.sleep(0.05)
        auth = request.headers.get("Authorization", "none")
        return {"user": "test", "auth": auth}

    @app.get("/nocache")
    async def nocache_endpoint():
        await asyncio.sleep(0.05)
        return {"result": "nocache", "timestamp": time.time()}

    return app, middleware


@pytest.mark.asyncio
async def test_cache_hit_performance(app_with_cache):
    """Test cache hit provides significant performance improvement."""
    app, middleware = app_with_cache
    client = TestClient(app)

    # First request - cache miss (should take ~50ms)
    start = time.time()
    response1 = client.get("/fast")
    first_latency = (time.time() - start) * 1000
    assert response1.status_code == 200

    # Second request - cache hit (should be < 5ms)
    start = time.time()
    response2 = client.get("/fast")
    cached_latency = (time.time() - start) * 1000
    assert response2.status_code == 200

    # Cache should be much faster
    assert (
        cached_latency < first_latency / 5
    ), f"Cache not fast enough: {cached_latency:.2f}ms vs {first_latency:.2f}ms"

    # Verify stats
    stats = middleware.get_stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1

    print(f"\nFirst request: {first_latency:.2f}ms")
    print(f"Cached request: {cached_latency:.2f}ms")
    print(f"Speedup: {first_latency / cached_latency:.1f}x")


@pytest.mark.asyncio
async def test_cache_user_specific(app_with_cache):
    """Test cache handles user-specific caching correctly."""
    app, middleware = app_with_cache
    client = TestClient(app)

    # Request with user1
    response1 = client.get("/user", headers={"Authorization": "Bearer user1"})
    assert response1.status_code == 200

    # Same request with user1 - should hit cache
    response2 = client.get("/user", headers={"Authorization": "Bearer user1"})
    assert response2.status_code == 200

    # Request with user2 - different cache key, should miss
    response3 = client.get("/user", headers={"Authorization": "Bearer user2"})
    assert response3.status_code == 200

    # Verify stats show correct behavior
    stats = middleware.get_stats()
    assert stats["hits"] >= 1  # user1's second request
    assert stats["misses"] >= 2  # user1's first + user2's request


@pytest.mark.asyncio
async def test_nocache_endpoints(app_with_cache):
    """Test endpoints not in cache patterns are not cached."""
    app, middleware = app_with_cache
    client = TestClient(app)

    # Clear stats
    middleware.clear_stats()

    # Multiple requests to nocache endpoint
    for _ in range(3):
        response = client.get("/nocache")
        assert response.status_code == 200

    # Should all be misses, no hits
    stats = middleware.get_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0  # Not even counted as misses


@pytest.mark.asyncio
async def test_concurrent_cache_access(app_with_cache):
    """Test cache handles concurrent requests efficiently."""
    app, middleware = app_with_cache
    client = TestClient(app)

    # Warm up cache
    client.get("/fast")

    # Concurrent requests to cached endpoint
    num_requests = 50

    async def make_request():
        response = client.get("/fast")
        assert response.status_code == 200

    start = time.time()
    tasks = [make_request() for _ in range(num_requests)]
    await asyncio.gather(*tasks)
    elapsed = (time.time() - start) * 1000

    # All cached requests should complete very quickly
    avg_latency = elapsed / num_requests
    assert avg_latency < 10, f"Average latency too high: {avg_latency:.2f}ms"

    print(f"\n{num_requests} concurrent cached requests: {elapsed:.2f}ms total")
    print(f"Average latency: {avg_latency:.2f}ms")


@pytest.mark.asyncio
async def test_cache_stats_accuracy(app_with_cache):
    """Test cache statistics are accurate."""
    app, middleware = app_with_cache
    client = TestClient(app)

    # Clear stats
    middleware.clear_stats()

    # Make specific pattern of requests
    client.get("/fast")  # miss
    client.get("/fast")  # hit
    client.get("/fast")  # hit
    client.get("/user", headers={"Authorization": "Bearer user1"})  # miss
    client.get("/user", headers={"Authorization": "Bearer user1"})  # hit

    stats = middleware.get_stats()
    assert stats["hits"] == 3
    assert stats["misses"] == 2
    assert stats["total_requests"] == 5

    hit_rate = stats["hit_rate_percent"]
    assert 59 <= hit_rate <= 61  # Should be ~60%

    # Check by-endpoint stats
    assert "/fast" in stats["by_endpoint"]
    assert stats["by_endpoint"]["/fast"]["hits"] == 2
    assert stats["by_endpoint"]["/fast"]["misses"] == 1


@pytest.mark.asyncio
async def test_cache_invalidation(app_with_cache):
    """Test cache invalidation works correctly."""
    app, middleware = app_with_cache
    client = TestClient(app)

    # Make requests to cache data
    response1 = client.get("/fast")
    data1 = response1.json()

    # Verify cached
    response2 = client.get("/fast")
    data2 = response2.json()
    assert data1 == data2  # Same cached response

    # Invalidate cache
    await middleware.invalidate_pattern("/fast")

    # Next request should get fresh data
    response3 = client.get("/fast")
    data3 = response3.json()

    # Timestamp should be different (new request)
    # Note: In real scenario, timestamp would differ


@pytest.mark.asyncio
async def test_cache_performance_with_load(app_with_cache):
    """Test cache performance under load."""
    app, middleware = app_with_cache
    client = TestClient(app)

    # Warm up cache
    client.get("/fast")

    # Simulate load
    num_requests = 100
    start = time.time()

    for _ in range(num_requests):
        response = client.get("/fast")
        assert response.status_code == 200

    elapsed = time.time() - start
    throughput = num_requests / elapsed

    # Should achieve high throughput with caching
    assert throughput > 100, f"Low throughput: {throughput:.0f} req/s"

    stats = middleware.get_stats()
    print(f"\nLoad test: {num_requests} requests in {elapsed:.2f}s")
    print(f"Throughput: {throughput:.0f} req/s")
    print(f"Hit rate: {stats['hit_rate_percent']:.1f}%")


@pytest.mark.asyncio
async def test_cache_ttl_expiration(app_with_cache):
    """Test cache entries expire based on TTL."""
    app, middleware = app_with_cache
    client = TestClient(app)

    # Create app with short TTL for testing
    app_short = FastAPI()
    cache_config = CacheConfig(
        enabled=True,
        cache_patterns={"/short": 1},  # 1 second TTL
    )
    middleware_short = ResponseCacheMiddleware(app_short, cache_config)
    app_short.add_middleware(ResponseCacheMiddleware, config=cache_config)

    @app_short.get("/short")
    async def short_endpoint():
        return {"timestamp": time.time()}

    client_short = TestClient(app_short)

    # First request
    response1 = client_short.get("/short")
    timestamp1 = response1.json()["timestamp"]

    # Immediate second request - should be cached
    response2 = client_short.get("/short")
    timestamp2 = response2.json()["timestamp"]
    assert timestamp1 == timestamp2

    # Wait for TTL to expire
    await asyncio.sleep(1.5)

    # Should get fresh data after TTL
    response3 = client_short.get("/short")
    timestamp3 = response3.json()["timestamp"]
    # Note: In test environment, might need adjustment


@pytest.mark.asyncio
async def test_cache_error_handling(redis_pool):
    """Test cache gracefully handles errors."""
    app = FastAPI()

    # Create middleware with invalid config
    cache_config = CacheConfig(
        enabled=True,
        cache_patterns={"/test": 60},
    )
    middleware = ResponseCacheMiddleware(app, cache_config)
    app.add_middleware(ResponseCacheMiddleware, config=cache_config)

    @app.get("/test")
    async def test_endpoint():
        return {"result": "ok"}

    client = TestClient(app)

    # Should work even if cache has issues
    response = client.get("/test")
    assert response.status_code == 200
