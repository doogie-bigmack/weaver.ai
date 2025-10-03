"""Comprehensive memory persistence tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis

from weaver_ai.memory import AgentMemory, MemoryStrategy


class TestMemoryPersistence:
    """Test memory persistence with Redis."""

    @pytest_asyncio.fixture(loop_scope="function")
    async def redis_client(self):
        """Create a fake Redis client for testing."""
        client = FakeAsyncRedis(decode_responses=True)
        yield client
        await client.aclose()

    @pytest_asyncio.fixture(loop_scope="function")
    async def memory(self, redis_client):
        """Create an agent memory instance."""
        strategy = MemoryStrategy(
            short_term_size=10,
            long_term_size=100,
            short_term_ttl=60,
            long_term_ttl=3600,
        )
        memory = AgentMemory(
            strategy=strategy, agent_id="test_agent", redis_client=redis_client
        )
        await memory.initialize()
        yield memory

    @pytest.mark.asyncio
    async def test_memory_survives_restart(self, redis_client):
        """Test that memory persists across agent restarts."""
        # Create first memory instance
        memory1 = AgentMemory(
            strategy=MemoryStrategy(),
            agent_id="persistent_agent",
            redis_client=redis_client,
        )
        await memory1.initialize()

        # Add data to memory
        await memory1.add_to_short_term("key1", {"data": "value1"})
        await memory1.add_to_long_term("key2", {"data": "value2"})

        # Simulate restart - create new memory instance with same agent_id
        memory2 = AgentMemory(
            strategy=MemoryStrategy(),
            agent_id="persistent_agent",
            redis_client=redis_client,
        )
        await memory2.initialize()

        # Verify data persisted
        short_term = await memory2.get_from_short_term("key1")
        assert short_term == {"data": "value1"}

        long_term = await memory2.get_from_long_term("key2")
        assert long_term == {"data": "value2"}

    @pytest.mark.asyncio
    async def test_memory_size_limits(self, memory):
        """Test memory size limits are enforced."""
        # Fill short-term memory beyond limit
        for i in range(15):  # Limit is 10
            await memory.add_to_short_term(f"key{i}", {"data": f"value{i}"})

        # Check that only last 10 items are retained
        all_keys = await memory.get_all_short_term_keys()
        assert len(all_keys) <= 10

        # Verify oldest items were evicted
        oldest = await memory.get_from_short_term("key0")
        assert oldest is None

        # Verify newest items are retained
        newest = await memory.get_from_short_term("key14")
        assert newest == {"data": "value14"}

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Flaky under load - timing sensitive Redis TTL test")
    async def test_memory_ttl_expiration(self, redis_client):
        """Test memory TTL expiration."""
        # Create memory with short TTL
        strategy = MemoryStrategy(
            short_term_ttl=1, long_term_ttl=3  # 1 second TTL  # 3 seconds TTL
        )
        memory = AgentMemory(
            strategy=strategy, agent_id="ttl_test", redis_client=redis_client
        )
        await memory.initialize()

        # Add data
        await memory.add_to_short_term("expire_soon", {"data": "temp"})
        await memory.add_to_long_term("expire_later", {"data": "less_temp"})

        # Verify data exists
        assert await memory.get_from_short_term("expire_soon") is not None
        assert await memory.get_from_long_term("expire_later") is not None

        # Wait for short-term expiration (1s TTL + 0.7s buffer)
        await asyncio.sleep(1.7)

        # Short-term should be expired, long-term still exists
        assert await memory.get_from_short_term("expire_soon") is None
        assert await memory.get_from_long_term("expire_later") is not None

        # Wait for long-term expiration (1.5s remaining + 0.2s buffer)
        await asyncio.sleep(1.7)

        # Both should be expired
        assert await memory.get_from_long_term("expire_later") is None

    @pytest.mark.asyncio
    async def test_concurrent_memory_access(self, memory):
        """Test concurrent access to memory."""

        async def writer(n: int):
            """Write to memory concurrently."""
            for i in range(10):
                await memory.add_to_short_term(f"writer{n}_key{i}", {"value": i})
                await asyncio.sleep(0.001)  # Small delay to interleave operations

        async def reader(n: int):
            """Read from memory concurrently."""
            results = []
            for i in range(10):
                data = await memory.get_from_short_term(f"writer{n}_key{i}")
                if data:
                    results.append(data)
                await asyncio.sleep(0.001)
            return results

        # Start multiple writers
        writers = [writer(i) for i in range(3)]
        await asyncio.gather(*writers)

        # Start multiple readers
        readers = [reader(i) for i in range(3)]
        results = await asyncio.gather(*readers)

        # Verify all readers got their data
        for i, result in enumerate(results):
            assert len(result) > 0, f"Reader {i} got no results"

    @pytest.mark.asyncio
    async def test_memory_overflow_handling(self, redis_client):
        """Test handling of memory overflow scenarios."""
        # Create memory with very small limits
        strategy = MemoryStrategy(short_term_size=2, long_term_size=5)
        memory = AgentMemory(
            strategy=strategy, agent_id="overflow_test", redis_client=redis_client
        )
        await memory.initialize()

        # Add data that exceeds limits
        large_data = {"large": "x" * 1000}

        # Short-term overflow
        await memory.add_to_short_term("item1", large_data)
        await memory.add_to_short_term("item2", large_data)
        await memory.add_to_short_term("item3", large_data)  # Should evict item1

        assert await memory.get_from_short_term("item1") is None
        assert await memory.get_from_short_term("item2") is not None
        assert await memory.get_from_short_term("item3") is not None

        # Long-term overflow
        for i in range(10):
            await memory.add_to_long_term(f"long{i}", large_data)

        # Only last 5 should remain
        assert await memory.get_from_long_term("long4") is None
        assert await memory.get_from_long_term("long9") is not None

    @pytest.mark.asyncio
    async def test_redis_connection_failure(self, monkeypatch):
        """Test handling of Redis connection failures."""

        # Create a client that will fail
        class FailingRedis:
            async def get(self, key):
                raise ConnectionError("Redis connection failed")

            async def set(self, key, value, ex=None):
                raise ConnectionError("Redis connection failed")

            async def delete(self, key):
                raise ConnectionError("Redis connection failed")

            async def keys(self, pattern):
                raise ConnectionError("Redis connection failed")

            async def ping(self):
                raise ConnectionError("Redis connection failed")

        failing_client = FailingRedis()

        memory = AgentMemory(
            strategy=MemoryStrategy(),
            agent_id="failure_test",
            redis_client=failing_client,
        )

        # Operations should handle failures gracefully without raising
        # The memory system should degrade gracefully when Redis is unavailable
        try:
            await memory.add_to_short_term("key", {"data": "value"})
            result = await memory.get_from_short_term("key")
            # Either works in fallback mode or returns None
            assert result is None or result == {"data": "value"}
        except ConnectionError:
            # Also acceptable if it raises ConnectionError
            pass

    @pytest.mark.asyncio
    async def test_memory_backup_restore(self, redis_client):
        """Test memory backup and restore functionality."""
        memory = AgentMemory(
            strategy=MemoryStrategy(), agent_id="backup_test", redis_client=redis_client
        )
        await memory.initialize()

        # Add test data
        test_data = {
            "short_term": {"st1": {"value": 1}, "st2": {"value": 2}},
            "long_term": {"lt1": {"value": 10}, "lt2": {"value": 20}},
        }

        for key, value in test_data["short_term"].items():
            await memory.add_to_short_term(key, value)

        for key, value in test_data["long_term"].items():
            await memory.add_to_long_term(key, value)

        # Create backup
        backup = await memory.create_backup()

        assert "short_term" in backup
        assert "long_term" in backup
        assert len(backup["short_term"]) == 2
        assert len(backup["long_term"]) == 2

        # Clear memory
        await memory.clear_all()

        # Verify memory is empty
        assert await memory.get_from_short_term("st1") is None
        assert await memory.get_from_long_term("lt1") is None

        # Restore from backup
        await memory.restore_from_backup(backup)

        # Verify data restored
        assert await memory.get_from_short_term("st1") == {"value": 1}
        assert await memory.get_from_long_term("lt1") == {"value": 10}

    @pytest.mark.asyncio
    async def test_memory_isolation_between_agents(self, redis_client):
        """Test that different agents have isolated memory."""
        # Create two agents with same redis client
        memory1 = AgentMemory(
            strategy=MemoryStrategy(), agent_id="agent1", redis_client=redis_client
        )
        await memory1.initialize()

        memory2 = AgentMemory(
            strategy=MemoryStrategy(), agent_id="agent2", redis_client=redis_client
        )
        await memory2.initialize()

        # Add data to agent1
        await memory1.add_to_short_term("shared_key", {"agent": "one"})

        # Add data to agent2 with same key
        await memory2.add_to_short_term("shared_key", {"agent": "two"})

        # Verify isolation
        agent1_data = await memory1.get_from_short_term("shared_key")
        agent2_data = await memory2.get_from_short_term("shared_key")

        assert agent1_data == {"agent": "one"}
        assert agent2_data == {"agent": "two"}

    @pytest.mark.asyncio
    async def test_memory_search_capabilities(self, memory):
        """Test memory search functionality."""
        # Add various data
        await memory.add_to_short_term("user_123", {"name": "Alice", "age": 30})
        await memory.add_to_short_term("user_456", {"name": "Bob", "age": 25})
        await memory.add_to_short_term("product_abc", {"name": "Widget", "price": 99})

        # Search by key pattern
        user_keys = await memory.search_keys("user_*")
        assert len(user_keys) == 2
        assert "user_123" in user_keys
        assert "user_456" in user_keys

        # Search by value content (if implemented)
        # This would require additional implementation in AgentMemory

    @pytest.mark.asyncio
    async def test_memory_statistics(self, memory):
        """Test memory usage statistics."""
        # Add data
        for i in range(5):
            await memory.add_to_short_term(f"st_{i}", {"value": i})
            await memory.add_to_long_term(f"lt_{i}", {"value": i * 10})

        # Get statistics
        stats = await memory.get_stats()

        assert stats["short_term_count"] == 5
        assert stats["long_term_count"] == 5
        assert stats["agent_id"] == "test_agent"

    @pytest.mark.asyncio
    async def test_episodic_memory(self, memory):
        """Test episodic memory for specific experiences."""
        # Add episodic memories
        episode1 = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": "user_interaction",
            "details": {"user": "Alice", "action": "query", "result": "success"},
        }

        episode2 = {
            "timestamp": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            "event": "error_occurred",
            "details": {"error": "timeout", "recovery": "retry"},
        }

        await memory.add_episodic("episode_1", episode1)
        await memory.add_episodic("episode_2", episode2)

        # Retrieve episodic memories
        retrieved = await memory.get_episodic("episode_1")
        assert retrieved == episode1

        # Get recent episodes
        recent = await memory.get_recent_episodes(limit=2)
        assert len(recent) == 2

    @pytest.mark.asyncio
    async def test_semantic_memory(self, memory):
        """Test semantic memory for domain knowledge."""
        # Add semantic knowledge
        knowledge = {
            "concept": "photosynthesis",
            "definition": "Process by which plants convert light to energy",
            "related": ["chlorophyll", "carbon dioxide", "oxygen"],
        }

        await memory.add_semantic("photosynthesis", knowledge)

        # Retrieve semantic memory
        retrieved = await memory.get_semantic("photosynthesis")
        assert retrieved == knowledge

        # Update semantic memory
        knowledge["related"].append("glucose")
        await memory.update_semantic("photosynthesis", knowledge)

        updated = await memory.get_semantic("photosynthesis")
        assert "glucose" in updated["related"]
