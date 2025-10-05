#!/usr/bin/env python3
"""Test Redis caching performance improvements."""

import asyncio
import statistics
import time

import httpx
import pytest


async def make_request(client: httpx.AsyncClient, query: str) -> tuple[float, bool]:
    """Make a request and return latency and cache status."""
    start = time.time()
    response = await client.post("http://localhost:8000/ask", json={"query": query})
    latency_ms = (time.time() - start) * 1000

    data = response.json()
    cached = data.get("cached", False)

    return latency_ms, cached


@pytest.mark.asyncio
async def test_cache_warmup():
    """Test cache warmup behavior."""
    print("\n=== Cache Warmup Test ===")

    queries = [
        "What is 2+2?",
        "Calculate 100 * 50",
        "What is the capital of France?",
        "Explain photosynthesis",
        "Convert 100 USD to EUR",
    ]

    async with httpx.AsyncClient() as client:
        # First pass - cold cache
        print("\nFirst pass (cold cache):")
        for query in queries:
            latency, cached = await make_request(client, query)
            print(
                f"  Query: '{query[:30]}...' - Latency: {latency:.2f}ms, Cached: {cached}"
            )

        # Second pass - warm cache
        print("\nSecond pass (warm cache):")
        for query in queries:
            latency, cached = await make_request(client, query)
            print(
                f"  Query: '{query[:30]}...' - Latency: {latency:.2f}ms, Cached: {cached}"
            )


@pytest.mark.asyncio
async def test_cache_hit_rate():
    """Test cache hit rate with repeated queries."""
    print("\n=== Cache Hit Rate Test ===")

    # Mix of repeated and unique queries
    queries = [
        "What is 2+2?",
        "What is 2+2?",  # Repeat
        "Calculate 10 * 10",
        "What is 2+2?",  # Repeat
        "Calculate 10 * 10",  # Repeat
        "What is 5+5?",
        "Calculate 10 * 10",  # Repeat
        "What is 2+2?",  # Repeat
        "What is 7+7?",
        "What is 5+5?",  # Repeat
    ]

    hits = 0
    misses = 0
    latencies_cached = []
    latencies_uncached = []

    async with httpx.AsyncClient() as client:
        for query in queries:
            latency, cached = await make_request(client, query)

            if cached:
                hits += 1
                latencies_cached.append(latency)
            else:
                misses += 1
                latencies_uncached.append(latency)

    hit_rate = (hits / (hits + misses)) * 100

    print("\nResults:")
    print(f"  Total requests: {hits + misses}")
    print(f"  Cache hits: {hits}")
    print(f"  Cache misses: {misses}")
    print(f"  Hit rate: {hit_rate:.1f}%")

    if latencies_cached:
        print("\nCached request latencies:")
        print(f"  Mean: {statistics.mean(latencies_cached):.2f}ms")
        print(f"  Median: {statistics.median(latencies_cached):.2f}ms")
        print(f"  Min: {min(latencies_cached):.2f}ms")
        print(f"  Max: {max(latencies_cached):.2f}ms")

    if latencies_uncached:
        print("\nUncached request latencies:")
        print(f"  Mean: {statistics.mean(latencies_uncached):.2f}ms")
        print(f"  Median: {statistics.median(latencies_uncached):.2f}ms")
        print(f"  Min: {min(latencies_uncached):.2f}ms")
        print(f"  Max: {max(latencies_uncached):.2f}ms")

    if latencies_cached and latencies_uncached:
        speedup = statistics.mean(latencies_uncached) / statistics.mean(
            latencies_cached
        )
        print(f"\nCache speedup: {speedup:.1f}x faster")


@pytest.mark.asyncio
async def test_concurrent_cache():
    """Test cache performance under concurrent load."""
    print("\n=== Concurrent Cache Test ===")

    query = "What is the meaning of life?"
    num_requests = 50

    async def make_concurrent_request(client: httpx.AsyncClient) -> tuple[float, bool]:
        return await make_request(client, query)

    async with httpx.AsyncClient() as client:
        # Warm up cache with first request
        await make_request(client, query)

        # Make concurrent requests
        start = time.time()
        tasks = [make_concurrent_request(client) for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start

        cached_count = sum(1 for _, cached in results if cached)
        latencies = [latency for latency, _ in results]

        print(f"\nResults for {num_requests} concurrent requests:")
        print(f"  Total time: {total_time*1000:.2f}ms")
        print(f"  Requests per second: {num_requests/total_time:.1f}")
        cache_pct = cached_count / num_requests * 100
        print(f"  Cached responses: {cached_count}/{num_requests} ({cache_pct:.1f}%)")
        print(f"  Mean latency: {statistics.mean(latencies):.2f}ms")
        print(f"  Median latency: {statistics.median(latencies):.2f}ms")
        print(f"  P95 latency: {sorted(latencies)[int(num_requests*0.95)]:.2f}ms")


async def get_cache_stats():
    """Get and display cache statistics."""
    print("\n=== Cache Statistics ===")

    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/cache/stats")
        stats = response.json()

        print("\nCache performance metrics:")
        if "cache_stats" in stats and "mock" in stats["cache_stats"]:
            mock_stats = stats["cache_stats"]["mock"]
            for key, value in mock_stats.items():
                print(f"  {key}: {value}")


async def main():
    """Run all cache performance tests."""
    print("=" * 60)
    print("Redis Cache Performance Testing")
    print("=" * 60)

    # Give services time to stabilize
    await asyncio.sleep(2)

    # Run tests
    await test_cache_warmup()
    await test_cache_hit_rate()
    await test_concurrent_cache()
    await get_cache_stats()

    print("\n" + "=" * 60)
    print("Testing Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
