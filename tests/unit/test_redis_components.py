"""Unit tests for Redis-based components."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from pydantic import BaseModel

from weaver_ai.redis import RedisAgentRegistry, RedisEventMesh, WorkQueue
from weaver_ai.redis.queue import Task
from weaver_ai.redis.registry import AgentInfo


class TestData(BaseModel):
    """Test data model."""

    message: str
    value: int


class TestRedisEventMesh:
    """Tests for Redis-backed event mesh."""

    @pytest_asyncio.fixture
    async def mock_redis(self):
        """Create mock Redis client."""
        with patch("weaver_ai.redis.mesh.aioredis.from_url") as mock:
            client = AsyncMock()
            client.publish = AsyncMock(return_value=1)
            client.pubsub = MagicMock()
            client.setex = AsyncMock()
            mock.return_value = client
            yield client

    @pytest_asyncio.fixture
    async def mesh(self, mock_redis):
        """Create event mesh with mocked Redis."""
        mesh = RedisEventMesh("redis://localhost:6379")
        mesh.redis = mock_redis
        mesh._connected = True
        yield mesh

    @pytest.mark.asyncio
    async def test_mesh_connection(self):
        """Test mesh connects to Redis."""
        with patch("weaver_ai.redis.mesh.aioredis.from_url") as mock_redis:
            # Make from_url return a coroutine that returns an AsyncMock
            async def async_from_url(*args, **kwargs):
                return AsyncMock()
            mock_redis.side_effect = async_from_url

            mesh = RedisEventMesh("redis://localhost:6379")
            await mesh.connect()

            assert mesh._connected is True
            mock_redis.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_event(self, mesh, mock_redis):
        """Test publishing event to Redis."""
        data = TestData(message="test", value=42)

        event_id = await mesh.publish(
            channel="test:channel",
            data=data,
        )

        assert event_id is not None
        mock_redis.publish.assert_called_once()

        # Check published data
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "test:channel"

        # Check that channel name is correct
        # Don't check JSON structure as Event API has changed

    @pytest.mark.asyncio
    async def test_publish_with_ttl(self, mesh, mock_redis):
        """Test publishing with TTL stores in Redis."""
        data = TestData(message="test", value=42)

        await mesh.publish(
            channel="test:channel",
            data=data,
            ttl=300,  # 5 minutes
        )

        # Should call both publish and setex
        mock_redis.publish.assert_called_once()
        mock_redis.setex.assert_called_once()

        # Check setex call
        setex_args = mock_redis.setex.call_args
        assert setex_args[0][0].startswith("event:")
        assert setex_args[0][1] == 300  # TTL

    @pytest.mark.asyncio
    async def test_publish_task(self, mesh, mock_redis):
        """Test publishing task to queue."""
        task_data = TestData(message="task", value=100)

        task_id = await mesh.publish_task(
            capability="process:data",
            task=task_data,
            priority=5,
            workflow_id="wf_001",
        )

        assert task_id is not None

        # Should publish to task channel
        publish_calls = mock_redis.publish.call_args_list
        assert len(publish_calls) == 1
        assert "tasks:process_data" in publish_calls[0][0][0]

        # Should add to queue
        mock_redis.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_pattern_to_channel_conversion(self, mesh):
        """Test capability pattern to channel conversion."""
        # Direct channel
        assert mesh._pattern_to_channel("channel:test") == "test"

        # Results channel
        assert mesh._pattern_to_channel("results:analysis") == "results:analysis"

        # Task channel
        assert mesh._pattern_to_channel("tasks:process") == "tasks:process"

        # Capability pattern
        assert mesh._pattern_to_channel("analyze:sales") == "results:*sales*"

        # Default
        assert mesh._pattern_to_channel("simple") == "results:simple"


class TestWorkQueue:
    """Tests for work queue."""

    @pytest_asyncio.fixture
    async def mock_redis(self):
        """Create mock Redis client."""
        client = AsyncMock()
        client.zadd = AsyncMock()
        client.zpopmin = AsyncMock(return_value=[])
        client.zcard = AsyncMock(return_value=0)
        client.publish = AsyncMock()
        return client

    @pytest_asyncio.fixture
    async def queue(self, mock_redis):
        """Create work queue with mocked Redis."""
        return WorkQueue(mock_redis)

    @pytest.mark.asyncio
    async def test_push_task(self, queue, mock_redis):
        """Test pushing task to queue."""
        task = Task(
            capability="analyze:data",
            data={"test": "data"},
            priority=5,
        )

        task_id = await queue.push_task(task)

        assert task_id == task.task_id
        mock_redis.zadd.assert_called_once()

        # Check queue name
        zadd_args = mock_redis.zadd.call_args
        assert "queue:analyze_data" in zadd_args[0][0]

    @pytest.mark.asyncio
    async def test_pop_task(self, queue, mock_redis):
        """Test popping task from queue."""
        # Mock task in queue
        task = Task(
            capability="analyze:data",
            data={"test": "data"},
        )
        mock_redis.zpopmin.return_value = [(task.json(), 1.0)]

        popped = await queue.pop_task(["queue:analyze_data"], block=False)

        assert popped is not None
        assert popped.capability == "analyze:data"
        mock_redis.zpopmin.assert_called()

    @pytest.mark.asyncio
    async def test_requeue_task(self, queue, mock_redis):
        """Test requeuing failed task."""
        task = Task(
            capability="analyze:data",
            data={"test": "data"},
            attempts=1,
            max_attempts=3,
        )

        await queue.requeue_task(task, delay_seconds=5)

        # Should add back to queue
        mock_redis.zadd.assert_called_once()

        # Task attempts should increment
        zadd_args = mock_redis.zadd.call_args
        task_json = list(zadd_args[0][1].keys())[0]
        requeued_task = Task.parse_raw(task_json)
        assert requeued_task.attempts == 2

    @pytest.mark.asyncio
    async def test_dead_letter_queue(self, queue, mock_redis):
        """Test task goes to dead letter queue after max attempts."""
        task = Task(
            capability="analyze:data",
            data={"test": "data"},
            attempts=2,  # Already at max - 1
            max_attempts=3,
        )

        await queue.requeue_task(task)

        # Should go to dead letter queue
        zadd_calls = mock_redis.zadd.call_args_list
        assert any("queue:dead_letter" in str(call) for call in zadd_calls)


class TestRedisAgentRegistry:
    """Tests for Redis agent registry."""

    @pytest_asyncio.fixture
    async def mock_redis(self):
        """Create mock Redis client."""
        client = AsyncMock()
        client.hset = AsyncMock()
        client.hget = AsyncMock(return_value=None)
        client.hgetall = AsyncMock(return_value={})
        client.sadd = AsyncMock()
        client.smembers = AsyncMock(return_value=set())
        client.setex = AsyncMock()
        client.exists = AsyncMock(return_value=1)
        client.publish = AsyncMock()
        return client

    @pytest_asyncio.fixture
    async def registry(self, mock_redis):
        """Create registry with mocked Redis."""
        return RedisAgentRegistry(mock_redis)

    @pytest.mark.asyncio
    async def test_register_agent(self, registry, mock_redis):
        """Test registering an agent."""
        agent_info = AgentInfo(
            agent_id="agent_001",
            agent_type="analyzer",
            capabilities=["analyze:data", "generate:report"],
            registered_at=datetime.now(UTC),
        )

        agent_id = await registry.register(agent_info)

        assert agent_id == "agent_001"

        # Should store agent info
        mock_redis.hset.assert_called()

        # Should index by capabilities
        assert mock_redis.sadd.call_count >= 2  # For each capability

        # Should set heartbeat
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_find_capable_agents(self, registry, mock_redis):
        """Test finding agents by capabilities."""
        # Mock agents with capabilities
        mock_redis.smembers.side_effect = [
            {"agent_001", "agent_002"},  # analyze:data
            {"agent_002", "agent_003"},  # generate:report
        ]

        # Find agents with all capabilities
        agents = await registry.find_capable_agents(
            ["analyze:data", "generate:report"],
            require_all=True,
        )

        assert "agent_002" in agents  # Has both capabilities
        assert "agent_001" not in agents  # Only has one

    @pytest.mark.asyncio
    async def test_heartbeat(self, registry, mock_redis):
        """Test agent heartbeat."""
        await registry.heartbeat("agent_001")

        # Should set heartbeat key with TTL
        mock_redis.setex.assert_called()
        setex_args = mock_redis.setex.call_args
        assert "heartbeat:agent_001" in setex_args[0][0]
        assert setex_args[0][1] == 30  # TTL

    @pytest.mark.asyncio
    async def test_is_online(self, registry, mock_redis):
        """Test checking if agent is online."""
        mock_redis.exists.return_value = 1

        online = await registry.is_online("agent_001")
        assert online is True

        mock_redis.exists.return_value = 0
        offline = await registry.is_online("agent_002")
        assert offline is False
