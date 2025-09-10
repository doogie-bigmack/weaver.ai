"""Integration tests for ResultPublisher secure result sharing."""

import asyncio
import time

import pytest
import pytest_asyncio
import redis.asyncio as redis

from weaver_ai.agents import ResultPublisher


@pytest_asyncio.fixture
async def redis_client():
    """Create a Redis client for testing."""
    client = await redis.from_url("redis://localhost:6379", db=15)  # Use test DB
    yield client
    # Cleanup
    await client.flushdb()
    await client.close()


@pytest_asyncio.fixture
async def publisher(redis_client):
    """Create a ResultPublisher for testing."""
    pub = ResultPublisher(redis_client=redis_client, namespace="test_results")
    yield pub
    await pub.disconnect()


class TestResultPublisher:
    """Test ResultPublisher functionality."""

    @pytest.mark.asyncio
    async def test_publish_and_retrieve(self, publisher):
        """Test basic publish and retrieve."""
        # Publish a result
        result = await publisher.publish(
            agent_id="agent1",
            data={"analysis": "test data", "score": 95},
            workflow_id="workflow1",
            tags={"type": "analysis"},
        )

        assert result.metadata.agent_id == "agent1"
        assert result.metadata.workflow_id == "workflow1"
        assert result.data == {"analysis": "test data", "score": 95}

        # Retrieve the result
        retrieved = await publisher.retrieve(result.metadata.result_id)
        assert retrieved is not None
        assert retrieved.data == {"analysis": "test data", "score": 95}
        assert retrieved.metadata.agent_id == "agent1"

    @pytest.mark.asyncio
    async def test_access_control(self, publisher):
        """Test capability-based access control."""
        # Publish with required capabilities
        result = await publisher.publish(
            agent_id="secure_agent",
            data={"secret": "classified"},
            capabilities_required=["security.read", "admin"],
        )

        assert result.access_token is not None  # Token generated

        # Try to retrieve without capabilities - should fail
        retrieved = await publisher.retrieve(
            result.metadata.result_id,
            agent_capabilities=["basic.read"],
        )
        assert retrieved is None  # Access denied

        # Retrieve with correct capability
        retrieved = await publisher.retrieve(
            result.metadata.result_id,
            agent_capabilities=["security.read"],
        )
        assert retrieved is not None
        assert retrieved.data == {"secret": "classified"}

        # Retrieve with access token
        retrieved = await publisher.retrieve(
            result.metadata.result_id,
            access_token=result.access_token,
        )
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_workflow_listing(self, publisher):
        """Test listing results by workflow."""
        workflow_id = "test_workflow"

        # Publish multiple results
        for i in range(3):
            await publisher.publish(
                agent_id=f"agent{i}",
                data={"step": i, "result": f"data{i}"},
                workflow_id=workflow_id,
            )
            await asyncio.sleep(0.1)  # Ensure different timestamps

        # List by workflow
        results = await publisher.list_by_workflow(workflow_id)
        assert len(results) == 3
        assert results[0].agent_id == "agent0"
        assert results[2].agent_id == "agent2"

    @pytest.mark.asyncio
    async def test_agent_listing(self, publisher):
        """Test listing results by agent."""
        agent_id = "test_agent"

        # Publish multiple results
        for i in range(5):
            await publisher.publish(
                agent_id=agent_id,
                data={"iteration": i},
            )

        # List by agent
        results = await publisher.list_by_agent(agent_id, limit=3)
        assert len(results) == 3
        # Should be in reverse chronological order
        assert results[0].agent_id == agent_id

    @pytest.mark.asyncio
    async def test_lineage_tracking(self, publisher):
        """Test result lineage tracking."""
        # Publish parent result
        parent = await publisher.publish(
            agent_id="parent_agent",
            data={"stage": "initial"},
        )

        # Publish child results
        child1 = await publisher.publish(
            agent_id="child_agent1",
            data={"stage": "processing"},
            parent_result_id=parent.metadata.result_id,
        )

        child2 = await publisher.publish(
            agent_id="child_agent2",
            data={"stage": "analysis"},
            parent_result_id=parent.metadata.result_id,
        )

        # Get lineage
        lineage = await publisher.get_lineage(parent.metadata.result_id)
        assert len(lineage) >= 1
        assert lineage[0].result_id == parent.metadata.result_id

        # Children should be accessible through lineage
        child_ids = {child1.metadata.result_id, child2.metadata.result_id}
        lineage_ids = {r.result_id for r in lineage}
        assert child_ids.issubset(lineage_ids)

    @pytest.mark.asyncio
    async def test_ttl_expiry(self, publisher):
        """Test TTL expiry of results."""
        # Publish with short TTL
        result = await publisher.publish(
            agent_id="temp_agent",
            data={"temporary": True},
            ttl_seconds=1,  # 1 second TTL
        )

        # Should be retrievable immediately
        retrieved = await publisher.retrieve(result.metadata.result_id)
        assert retrieved is not None

        # Wait for expiry
        await asyncio.sleep(2)

        # Should be expired
        retrieved = await publisher.retrieve(result.metadata.result_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_large_data_handling(self, publisher):
        """Test handling of large data."""
        # Create large data
        large_data = {"key": "x" * 10000, "array": list(range(1000))}

        # Publish large result
        result = await publisher.publish(
            agent_id="large_agent",
            data=large_data,
        )

        assert result.metadata.size_bytes > 10000

        # Should be retrievable
        retrieved = await publisher.retrieve(result.metadata.result_id)
        assert retrieved is not None
        assert retrieved.data == large_data

    @pytest.mark.asyncio
    async def test_concurrent_publishing(self, publisher):
        """Test concurrent publishing from multiple agents."""
        workflow_id = "concurrent_workflow"

        async def publish_result(agent_id: str, delay: float):
            await asyncio.sleep(delay)
            return await publisher.publish(
                agent_id=agent_id,
                data={"agent": agent_id, "timestamp": time.time()},
                workflow_id=workflow_id,
            )

        # Publish concurrently
        tasks = [publish_result(f"agent{i}", i * 0.1) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5

        # All should be retrievable
        for result in results:
            retrieved = await publisher.retrieve(result.metadata.result_id)
            assert retrieved is not None

        # Workflow should have all results
        workflow_results = await publisher.list_by_workflow(workflow_id)
        assert len(workflow_results) == 5


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
