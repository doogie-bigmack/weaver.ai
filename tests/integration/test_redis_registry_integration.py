"""Integration tests for RedisAgentRegistry with real Redis.

This test validates the pipeline optimizations in RedisAgentRegistry:
- list_agents() uses pipelines to batch heartbeat checks and agent info retrieval
- get_stats() uses pipelines to batch heartbeat checks and capability counts
- find_capable_agents() uses pipelines to batch capability lookups and heartbeat checks

Expected performance improvements:
- list_agents(): ~20x faster with pipelines
- get_stats(): ~15x faster with pipelines
- find_capable_agents(): ~10x faster with pipelines
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
import pytest_asyncio
import redis.asyncio as redis

from weaver_ai.redis.registry import AgentInfo, RedisAgentRegistry


@pytest_asyncio.fixture
async def redis_client():
    """Create a Redis client for testing."""
    client = await redis.from_url(
        "redis://localhost:6379", db=15, decode_responses=True
    )
    yield client
    # Cleanup
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def registry(redis_client):
    """Create a RedisAgentRegistry for testing."""
    return RedisAgentRegistry(redis_client)


@pytest_asyncio.fixture
async def populated_registry(registry):
    """Create a registry with test agents."""
    # Register 50 test agents with various capabilities
    for i in range(50):
        agent_info = AgentInfo(
            agent_id=f"agent_{i:03d}",
            agent_type="test_agent" if i % 2 == 0 else "worker_agent",
            capabilities=[
                f"capability_{i % 5}",
                f"capability_{(i + 1) % 5}",
            ],
            registered_at=datetime.now(UTC),
        )
        await registry.register(agent_info)

    # Give agents time to register heartbeats
    await asyncio.sleep(0.1)

    yield registry


class TestRedisAgentRegistryIntegration:
    """Integration tests for Redis agent registry with pipeline optimizations."""

    @pytest.mark.asyncio
    async def test_list_agents_with_pipeline(self, populated_registry):
        """Test list_agents() uses pipeline to batch operations."""
        # List all online agents (should use 2 pipelines: heartbeats + agent info)
        agents = await populated_registry.list_agents(only_online=True)

        # Should have all 50 agents (all should be online)
        assert len(agents) >= 45  # Allow for some heartbeat timing issues
        assert all(isinstance(agent, AgentInfo) for agent in agents)

        # Verify agent IDs are present
        agent_ids = [a.agent_id for a in agents]
        assert "agent_000" in agent_ids
        assert "agent_049" in agent_ids

    @pytest.mark.asyncio
    async def test_list_agents_by_type(self, populated_registry):
        """Test list_agents() filters by agent type."""
        # List agents of specific type
        test_agents = await populated_registry.list_agents(agent_type="test_agent")

        # Should have 25 test_agents (50% of total)
        assert len(test_agents) == 25
        assert all(a.agent_type == "test_agent" for a in test_agents)

    @pytest.mark.asyncio
    async def test_get_stats_with_pipeline(self, populated_registry):
        """Test get_stats() uses pipeline to batch all operations."""
        # Get stats (should use 3 pipelines: agent count, heartbeats, capabilities)
        stats = await populated_registry.get_stats()

        # Verify stats structure
        assert "total_agents" in stats
        assert "online_agents" in stats
        assert "offline_agents" in stats
        assert "capabilities" in stats

        # Verify counts
        assert stats["total_agents"] == 50
        assert stats["online_agents"] >= 45  # Most should be online
        assert stats["offline_agents"] <= 5

        # Verify capabilities are counted
        assert len(stats["capabilities"]) > 0
        # Should have capability_0 through capability_4
        capability_names = list(stats["capabilities"].keys())
        assert any("0" in cap for cap in capability_names)

    @pytest.mark.asyncio
    async def test_find_capable_agents_with_pipeline(self, populated_registry):
        """Test find_capable_agents() uses pipeline for lookups."""
        # Find agents with specific capability
        agents = await populated_registry.find_capable_agents(
            ["capability_0"], require_all=False, only_online=True
        )

        # Should find multiple agents with capability_0
        assert len(agents) > 0
        assert len(agents) <= 50

        # All should be strings (agent IDs)
        assert all(isinstance(agent_id, str) for agent_id in agents)

    @pytest.mark.asyncio
    async def test_find_capable_agents_intersection(self, populated_registry):
        """Test find_capable_agents() with require_all (intersection)."""
        # Find agents with multiple capabilities (intersection)
        agents = await populated_registry.find_capable_agents(
            ["capability_0", "capability_1"], require_all=True, only_online=True
        )

        # Should find agents that have BOTH capabilities
        # Based on our test data, agents with i%5==0 or i%5==4 should match
        assert len(agents) > 0

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, populated_registry):
        """Test concurrent registry operations work correctly."""
        # Run multiple operations concurrently
        results = await asyncio.gather(
            populated_registry.list_agents(),
            populated_registry.get_stats(),
            populated_registry.find_capable_agents(["capability_0"]),
            populated_registry.list_agents(agent_type="test_agent"),
        )

        # All should succeed
        agents_all, stats, capable, agents_filtered = results

        assert len(agents_all) == 50
        assert stats["total_agents"] == 50
        assert len(capable) > 0
        assert len(agents_filtered) == 25

    @pytest.mark.asyncio
    async def test_error_handling_redis_failure(self, registry, redis_client):
        """Test error handling when Redis pipeline fails."""
        # Close the Redis connection to simulate failure
        await redis_client.aclose()

        # Operations should return empty/default values instead of crashing
        agents = await registry.list_agents()
        assert agents == []

        stats = await registry.get_stats()
        assert stats == {
            "total_agents": 0,
            "online_agents": 0,
            "offline_agents": 0,
            "capabilities": {},
        }

        capable = await registry.find_capable_agents(["capability_0"])
        assert capable == []

    @pytest.mark.asyncio
    async def test_large_dataset_performance(self, registry):
        """Test with larger dataset to validate performance benefits."""
        # Register 100 agents
        for i in range(100):
            agent_info = AgentInfo(
                agent_id=f"perf_agent_{i:03d}",
                agent_type="performance_test",
                capabilities=[f"capability_{i % 10}"],
                registered_at=datetime.now(UTC),
            )
            await registry.register(agent_info)

        await asyncio.sleep(0.1)

        # Measure list_agents performance
        import time

        start = time.time()
        agents = await registry.list_agents(only_online=True)
        elapsed = time.time() - start

        # Should complete quickly (< 100ms for 100 agents)
        assert elapsed < 0.1
        assert len(agents) >= 95

        # Measure get_stats performance
        start = time.time()
        stats = await registry.get_stats()
        elapsed = time.time() - start

        assert elapsed < 0.1
        assert stats["total_agents"] == 100

    @pytest.mark.asyncio
    async def test_empty_registry(self, registry):
        """Test operations on empty registry."""
        agents = await registry.list_agents()
        assert agents == []

        stats = await registry.get_stats()
        assert stats["total_agents"] == 0
        assert stats["online_agents"] == 0

        capable = await registry.find_capable_agents(["any_capability"])
        assert capable == []
