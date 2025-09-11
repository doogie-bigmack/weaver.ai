"""Unit tests for ResultPublisher without Redis dependency."""

import json
from unittest.mock import AsyncMock

import pytest

from weaver_ai.agents import ResultPublisher


class TestResultPublisherUnit:
    """Unit tests for ResultPublisher."""

    @pytest.mark.asyncio
    async def test_publish_basic(self):
        """Test basic publishing functionality."""
        # Create publisher with mock Redis
        publisher = ResultPublisher()
        publisher.redis = AsyncMock()
        publisher._connected = True

        # Mock Redis operations
        publisher.redis.setex = AsyncMock(return_value=True)
        publisher.redis.sadd = AsyncMock(return_value=1)
        publisher.redis.zadd = AsyncMock(return_value=1)
        publisher.redis.expire = AsyncMock(return_value=True)

        # Publish a result
        result = await publisher.publish(
            agent_id="test_agent",
            data={"test": "data"},
            workflow_id="test_workflow",
        )

        # Verify result structure
        assert result.metadata.agent_id == "test_agent"
        assert result.data == {"test": "data"}
        assert result.metadata.workflow_id == "test_workflow"
        assert result.metadata.size_bytes > 0

        # Verify Redis calls were made
        assert publisher.redis.setex.call_count >= 2  # Data and metadata
        publisher.redis.sadd.assert_called()  # Workflow index
        publisher.redis.zadd.assert_called()  # Agent index

    @pytest.mark.asyncio
    async def test_publish_with_capabilities(self):
        """Test publishing with capability requirements."""
        publisher = ResultPublisher()
        publisher.redis = AsyncMock()
        publisher._connected = True

        publisher.redis.setex = AsyncMock(return_value=True)
        publisher.redis.sadd = AsyncMock(return_value=1)
        publisher.redis.zadd = AsyncMock(return_value=1)
        publisher.redis.expire = AsyncMock(return_value=True)

        # Publish with capabilities
        result = await publisher.publish(
            agent_id="secure_agent",
            data={"secret": "data"},
            capabilities_required=["security.read", "admin"],
        )

        # Should generate access token
        assert result.access_token is not None
        assert result.access_token.startswith("tok_")
        assert result.metadata.capabilities_required == ["security.read", "admin"]

    @pytest.mark.asyncio
    async def test_retrieve_with_access_control(self):
        """Test retrieval with access control."""
        publisher = ResultPublisher()
        publisher.redis = AsyncMock()
        publisher._connected = True

        # Mock metadata with capabilities
        metadata = {
            "result_id": "test123",
            "agent_id": "agent1",
            "capabilities_required": ["security.read"],
            "ttl_seconds": 3600,
            "timestamp": 1234567890,
            "version": 1,
            "size_bytes": 100,
        }

        # Mock Redis get operations
        publisher.redis.get = AsyncMock(
            side_effect=[
                json.dumps(metadata),  # Metadata
                json.dumps({"data": "secret"}),  # Data
            ]
        )

        # Try without capabilities - should fail
        result = await publisher.retrieve(
            "test123",
            agent_capabilities=["basic.read"],
        )
        assert result is None

        # Reset mock
        publisher.redis.get = AsyncMock(
            side_effect=[
                json.dumps(metadata),  # Metadata
                json.dumps({"data": "secret"}),  # Data
            ]
        )

        # Try with correct capability - should succeed
        result = await publisher.retrieve(
            "test123",
            agent_capabilities=["security.read"],
        )
        assert result is not None
        assert result.data == {"data": "secret"}

    @pytest.mark.asyncio
    async def test_list_by_workflow(self):
        """Test listing results by workflow."""
        publisher = ResultPublisher()
        publisher.redis = AsyncMock()
        publisher._connected = True

        # Mock workflow members
        publisher.redis.smembers = AsyncMock(
            return_value=[b"result1", b"result2", b"result3"]
        )

        # Mock metadata retrieval
        metadata = {
            "result_id": "result1",
            "agent_id": "agent1",
            "capabilities_required": [],
            "ttl_seconds": 3600,
            "timestamp": 1234567890,
            "version": 1,
            "size_bytes": 100,
        }

        publisher.redis.get = AsyncMock(return_value=json.dumps(metadata))

        # List by workflow
        results = await publisher.list_by_workflow("test_workflow")

        # Should have results
        assert len(results) > 0
        publisher.redis.smembers.assert_called_once()

    @pytest.mark.asyncio
    async def test_lineage_tracking(self):
        """Test result lineage tracking."""
        publisher = ResultPublisher()
        publisher.redis = AsyncMock()
        publisher._connected = True

        # Setup for parent publish
        publisher.redis.setex = AsyncMock(return_value=True)
        publisher.redis.sadd = AsyncMock(return_value=1)
        publisher.redis.zadd = AsyncMock(return_value=1)
        publisher.redis.expire = AsyncMock(return_value=True)

        # Publish parent
        parent = await publisher.publish(
            agent_id="parent_agent",
            data={"stage": "initial"},
        )

        # Publish child with parent reference
        child = await publisher.publish(
            agent_id="child_agent",
            data={"stage": "processing"},
            parent_result_id=parent.metadata.result_id,
        )

        # Verify lineage was tracked
        assert child.metadata.parent_result_id == parent.metadata.result_id

        # Verify Redis calls for lineage
        lineage_key = f"results:lineage:{parent.metadata.result_id}"
        publisher.redis.sadd.assert_any_call(lineage_key, child.metadata.result_id)

    @pytest.mark.asyncio
    async def test_access_token_generation(self):
        """Test access token generation and verification."""
        publisher = ResultPublisher()

        # Generate token
        result_id = "test_result_123"
        token = publisher._generate_access_token(result_id)

        # Verify format
        assert token.startswith(f"tok_{result_id}_")

        # Verify validation
        assert publisher._verify_access_token(result_id, token) is True
        assert publisher._verify_access_token(result_id, "wrong_token") is False
        assert publisher._verify_access_token("wrong_id", token) is False

    @pytest.mark.asyncio
    async def test_data_serialization(self):
        """Test different data types are serialized correctly."""
        publisher = ResultPublisher()
        publisher.redis = AsyncMock()
        publisher._connected = True

        publisher.redis.setex = AsyncMock(return_value=True)
        publisher.redis.sadd = AsyncMock(return_value=1)
        publisher.redis.zadd = AsyncMock(return_value=1)
        publisher.redis.expire = AsyncMock(return_value=True)

        # Test dict
        result = await publisher.publish(
            agent_id="agent1",
            data={"key": "value"},
        )
        assert result.data == {"key": "value"}

        # Test list
        result = await publisher.publish(
            agent_id="agent2",
            data=[1, 2, 3],
        )
        assert result.data == [1, 2, 3]

        # Test string
        result = await publisher.publish(
            agent_id="agent3",
            data="plain text",
        )
        assert result.data == "plain text"

    @pytest.mark.asyncio
    async def test_ttl_configuration(self):
        """Test TTL configuration for results."""
        publisher = ResultPublisher()
        publisher.redis = AsyncMock()
        publisher._connected = True

        publisher.redis.setex = AsyncMock(return_value=True)
        publisher.redis.sadd = AsyncMock(return_value=1)
        publisher.redis.zadd = AsyncMock(return_value=1)
        publisher.redis.expire = AsyncMock(return_value=True)

        # Publish with custom TTL
        custom_ttl = 7200
        result = await publisher.publish(
            agent_id="agent1",
            data={"test": "data"},
            ttl_seconds=custom_ttl,
        )

        # Verify TTL was set
        assert result.metadata.ttl_seconds == custom_ttl

        # Verify Redis setex was called with correct TTL
        calls = publisher.redis.setex.call_args_list
        for call in calls:
            # Check that TTL argument matches
            if len(call[0]) >= 2:
                assert call[0][1] == custom_ttl


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
