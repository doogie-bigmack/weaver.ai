# Performance Optimization Guide

This document describes the performance optimizations implemented in Weaver AI, including centralized Redis connection pooling, HTTP response caching, and performance monitoring.

## Overview

The performance optimization implementation provides:

1. **Centralized Redis Connection Pool** - Shared connection pool across all components
2. **HTTP Response Caching** - FastAPI middleware for caching frequently accessed endpoints
3. **Performance Metrics** - `/metrics` endpoint exposing cache and pool statistics
4. **Comprehensive Testing** - Performance tests validating improvements

## Performance Improvements

### Before Optimization
- Each component created its own Redis connections (4-6 connections per component)
- No response caching (every request hit backend)
- No performance visibility

### After Optimization
- Single shared connection pool (100 connections max, reused across all components)
- Sub-millisecond response times for cached endpoints
- Real-time performance metrics and monitoring

**Expected Performance Gains:**
- 90%+ reduction in Redis connection overhead
- 95%+ faster response times for cacheable endpoints (/health, /whoami, /metrics)
- 80%+ reduction in backend load for frequently accessed endpoints

## Architecture

### 1. Centralized Redis Connection Pool

**Location:** `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/connection_pool.py`

A singleton connection pool shared across all Redis-based components:

```python
from weaver_ai.redis.connection_pool import (
    RedisPoolConfig,
    init_redis_pool,
    get_redis_pool,
    close_redis_pool,
    get_pool_stats,
)

# Initialize pool (done in gateway lifespan)
config = RedisPoolConfig(
    host="localhost",
    port=6379,
    max_connections=100,  # Shared across all components
)
await init_redis_pool(config)

# Get client from pool
redis_client = await get_redis_pool()
await redis_client.ping()

# Get pool statistics
stats = get_pool_stats()
```

**Key Features:**
- Connection reuse eliminates TCP handshake overhead
- Configurable pool size and timeouts
- Health monitoring and automatic reconnection
- Connection statistics for monitoring
- Thread-safe singleton pattern

### 2. HTTP Response Caching Middleware

**Location:** `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/middleware/cache.py`

FastAPI middleware that caches HTTP responses at the gateway level:

```python
from weaver_ai.middleware import ResponseCacheMiddleware, CacheConfig

# Configure caching
cache_config = CacheConfig(
    enabled=True,
    cache_patterns={
        "/health": 60,    # Cache for 60 seconds
        "/whoami": 30,    # Cache for 30 seconds
        "/metrics": 10,   # Cache for 10 seconds
    },
)

# Add middleware to FastAPI app
app.add_middleware(ResponseCacheMiddleware, config=cache_config)
```

**Key Features:**
- Pattern-based endpoint caching with configurable TTLs
- User-specific caching (includes Authorization header in cache key)
- Cache statistics tracking (hits, misses, latency saved)
- Per-endpoint statistics
- Automatic cache invalidation support

### 3. Performance Metrics Endpoint

**Endpoint:** `GET /metrics`

Returns comprehensive performance metrics:

```json
{
  "service": "weaver-ai",
  "status": "healthy",
  "http_cache": {
    "hits": 150,
    "misses": 25,
    "errors": 0,
    "hit_rate_percent": 85.71,
    "total_requests": 175,
    "total_latency_saved_ms": 3750.00,
    "avg_latency_saved_ms": 25.00,
    "by_endpoint": {
      "/health": {
        "hits": 100,
        "misses": 5
      },
      "/whoami": {
        "hits": 50,
        "misses": 20
      }
    }
  },
  "redis_pool": {
    "pool_initialized_at": 1696521600.0,
    "last_health_check": 1696521650.0,
    "config": {
      "max_connections": 100,
      "host": "localhost",
      "port": 6379
    },
    "pool_info": {
      "max_connections": 100,
      "available_connections": 95,
      "in_use_connections": 5
    },
    "uptime_seconds": 50.0,
    "uptime_hours": 0.01,
    "seconds_since_last_health_check": 5.0,
    "total_commands_executed": 1000,
    "total_errors": 0
  }
}
```

## Component Integration

### Updated Components

All Redis-using components now use the shared connection pool:

1. **Redis Cache** (`weaver_ai/cache/redis_cache.py`)
   - Uses `get_redis_pool()` instead of creating connections
   - Maintains intelligent TTL strategies

2. **Redis Registry** (`weaver_ai/redis/registry.py`)
   - Already optimized with pipeline batching
   - Now uses shared pool for connections

3. **Gateway** (`weaver_ai/gateway.py`)
   - Initializes pool on startup via lifespan
   - Adds caching middleware
   - Exposes `/metrics` endpoint

### Usage Example

```python
from weaver_ai.redis.connection_pool import get_redis_pool
from weaver_ai.cache.redis_cache import RedisCache, CacheConfig

# Components automatically use shared pool
redis_client = await get_redis_pool()

# Redis cache uses shared pool
cache = RedisCache(CacheConfig())
await cache.connect()  # Connects to shared pool
```

## Configuration

### Redis Pool Configuration

Configure via `RedisPoolConfig`:

```python
config = RedisPoolConfig(
    host="localhost",
    port=6379,
    db=0,
    password=None,
    max_connections=100,              # Total connections for all components
    socket_timeout=5.0,               # Socket timeout in seconds
    socket_connect_timeout=5.0,       # Connect timeout in seconds
    socket_keepalive=True,            # Enable TCP keepalive
    health_check_interval=30,         # Health check interval in seconds
    retry_on_timeout=True,            # Retry on timeout
)
```

### Cache Configuration

Configure via `CacheConfig`:

```python
config = CacheConfig(
    enabled=True,
    cache_patterns={
        "/health": 60,        # Cache health checks for 1 minute
        "/whoami": 30,        # Cache auth info for 30 seconds
        "/metrics": 10,       # Cache metrics for 10 seconds
    },
    cache_methods=["GET", "HEAD"],
    include_query_params=True,
    include_headers=["Authorization"],
    track_stats=True,
)
```

## Performance Testing

### Running Performance Tests

```bash
# Test connection pool performance
python3 -m pytest tests/performance/test_connection_pool.py -v

# Test cache middleware performance
python3 -m pytest tests/performance/test_cache_middleware.py -v

# Test metrics endpoint performance
python3 -m pytest tests/performance/test_metrics_endpoint.py -v

# Run all performance tests
python3 -m pytest tests/performance/ -v
```

### Performance Benchmarks

**Connection Pool:**
- Concurrent operations: 1000+ ops/second
- Connection reuse: 100 commands on 10 connections in < 1 second
- Pool overhead: < 1ms per operation

**Response Caching:**
- Cache hit latency: < 5ms
- First request: 10-50ms (backend call)
- Cached request: < 5ms (90%+ faster)
- Throughput: 100+ req/s for cached endpoints

**Metrics Endpoint:**
- Average latency: < 50ms
- Max latency: < 100ms
- Cached latency: < 10ms

## Monitoring

### Key Metrics to Monitor

1. **Cache Performance:**
   - `http_cache.hit_rate_percent` - Should be > 80% for cacheable endpoints
   - `http_cache.avg_latency_saved_ms` - Latency improvement per request
   - `http_cache.by_endpoint` - Per-endpoint cache effectiveness

2. **Redis Pool Health:**
   - `redis_pool.pool_info.available_connections` - Should be > 0
   - `redis_pool.pool_info.in_use_connections` - Should be < max_connections
   - `redis_pool.total_errors` - Should be 0 or very low

3. **Performance Indicators:**
   - Response time for `/health` - Should be < 10ms (cached)
   - Response time for `/whoami` - Should be < 20ms (cached)
   - Redis pool uptime - Should track application uptime

### Alerting Thresholds

```yaml
alerts:
  cache_hit_rate_low:
    condition: http_cache.hit_rate_percent < 70
    severity: warning

  redis_pool_exhausted:
    condition: redis_pool.pool_info.available_connections < 5
    severity: critical

  high_error_rate:
    condition: redis_pool.total_errors > 100
    severity: critical
```

## Troubleshooting

### Common Issues

**1. Pool Not Initialized Error**
```
PoolNotInitializedError: Redis pool not initialized. Call init_redis_pool() first.
```
**Solution:** Ensure pool is initialized in application lifespan:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis_pool(config)
    yield
    await close_redis_pool()
```

**2. Connection Pool Exhausted**
```
redis.exceptions.ConnectionError: Too many connections
```
**Solution:** Increase `max_connections` or reduce concurrent load:
```python
config = RedisPoolConfig(max_connections=200)
```

**3. Cache Not Working**
```
http_cache.hits: 0
```
**Solution:** Verify endpoints are in `cache_patterns` and requests match cache criteria.

### Debug Mode

Enable debug logging:
```python
import logging
logging.getLogger("weaver_ai.redis.connection_pool").setLevel(logging.DEBUG)
logging.getLogger("weaver_ai.middleware.cache").setLevel(logging.DEBUG)
```

## Best Practices

1. **Connection Pool Sizing:**
   - Start with 50-100 connections
   - Monitor `in_use_connections` under load
   - Increase if pool frequently exhausted

2. **Cache TTL Strategy:**
   - Static data: 1-24 hours
   - User-specific data: 30-300 seconds
   - Health checks: 10-60 seconds
   - Metrics: 5-10 seconds

3. **Performance Monitoring:**
   - Monitor `/metrics` endpoint regularly
   - Track cache hit rate (target > 80%)
   - Alert on pool exhaustion
   - Review per-endpoint statistics

4. **Load Testing:**
   - Test with realistic concurrent users
   - Verify cache effectiveness under load
   - Monitor connection pool utilization
   - Measure latency improvements

## Future Enhancements

Potential improvements:

1. **Advanced Caching:**
   - Cache stampede prevention
   - Probabilistic early expiration
   - Cache warming strategies
   - Multi-tier caching (L1: memory, L2: Redis)

2. **Pool Optimizations:**
   - Dynamic pool sizing based on load
   - Circuit breaker for Redis failures
   - Connection health checks
   - Automatic retry with exponential backoff

3. **Monitoring:**
   - Prometheus metrics export
   - Grafana dashboard templates
   - Performance analytics
   - Anomaly detection

## References

- [Redis Connection Pooling Best Practices](https://redis.io/docs/clients/python/)
- [FastAPI Middleware Guide](https://fastapi.tiangolo.com/advanced/middleware/)
- [HTTP Caching Strategies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching)
