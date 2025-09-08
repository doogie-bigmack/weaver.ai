"""Unit tests for agent framework."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from pydantic import BaseModel

from weaver_ai.agents import BaseAgent, Capability, CapabilityMatcher, agent
from weaver_ai.agents.base import Result
from weaver_ai.events import Event
from weaver_ai.memory import MemoryStrategy


class TestData(BaseModel):
    """Test data model."""

    value: str
    number: int


class TestBaseAgent:
    """Tests for BaseAgent class."""

    @pytest_asyncio.fixture
    async def base_agent(self):
        """Create a basic agent for testing."""
        agent = BaseAgent(
            agent_type="test",
            capabilities=["test:data", "process:numbers"],
        )
        yield agent

    def test_agent_creation(self):
        """Test agent can be created with defaults."""
        agent = BaseAgent()
        assert agent.agent_id
        assert agent.agent_type == "base"
        assert agent.version == "1.0.0"
        assert agent.capabilities == []

    def test_agent_with_capabilities(self):
        """Test agent with capabilities."""
        agent = BaseAgent(
            agent_type="analyzer",
            capabilities=["analyze:data", "generate:report"],
        )
        assert agent.agent_type == "analyzer"
        assert len(agent.capabilities) == 2
        assert "analyze:data" in agent.capabilities

    @pytest.mark.asyncio
    async def test_agent_initialization(self, base_agent):
        """Test agent initialization with mock Redis."""
        with patch("weaver_ai.agents.base.RedisEventMesh") as mock_mesh:
            with patch("weaver_ai.agents.base.aioredis.from_url") as mock_redis:
                mock_redis.return_value = AsyncMock()
                mock_mesh.return_value.connect = AsyncMock()

                await base_agent.initialize()

                assert base_agent.mesh is not None
                assert base_agent.registry is not None
                assert base_agent.memory is not None

    @pytest.mark.asyncio
    async def test_can_process(self, base_agent):
        """Test capability matching."""
        event = Event(
            event_type="TestData",
            data=TestData(value="test", number=42),
        )

        # Should match "test:data" capability
        assert await base_agent.can_process(event)

        # Non-matching event
        event2 = Event(
            event_type="OtherData",
            data={"value": "other"},
        )
        assert not await base_agent.can_process(event2)

    @pytest.mark.asyncio
    async def test_process_not_implemented(self, base_agent):
        """Test that process raises NotImplementedError."""
        event = Event(
            event_type="TestData",
            data=TestData(value="test", number=42),
        )

        with pytest.raises(NotImplementedError):
            await base_agent.process(event)


class TestAgentDecorator:
    """Tests for agent decorator."""

    def test_simple_agent_decorator(self):
        """Test creating agent with decorator."""

        @agent(
            agent_type="worker",
            capabilities=["work:hard", "process:data"],
        )
        class WorkerAgent:
            async def process(self, event):
                return Result(success=True, data={"processed": True})

        worker = WorkerAgent()
        assert worker.agent_type == "worker"
        assert "work:hard" in worker.capabilities
        assert hasattr(worker, "process")

    def test_agent_with_memory_strategy(self):
        """Test agent with predefined memory strategy."""

        @agent(
            agent_type="analyst",
            memory_strategy="analyst",
        )
        class AnalystAgent:
            pass

        analyst = AnalystAgent()
        assert (
            analyst.memory_strategy.long_term.max_size_mb == 10240
        )  # 10GB for analyst
        assert analyst.memory_strategy.semantic.enabled is True


class TestCapabilities:
    """Tests for capability system."""

    def test_capability_creation(self):
        """Test creating capabilities."""
        cap = Capability(
            name="analyze:sales",
            description="Analyze sales data",
            confidence=0.9,
        )

        assert cap.name == "analyze:sales"
        assert cap.confidence == 0.9

    def test_capability_matching(self):
        """Test capability matches event type."""
        cap = Capability(name="analyze:sales")

        assert cap.matches("analyze_sales_data")
        assert cap.matches("sales_analysis")
        assert not cap.matches("generate_report")

    def test_capability_matcher_coarse(self):
        """Test coarse capability matching."""
        capabilities = ["analyze:data", "generate:report", "validate"]

        matches = CapabilityMatcher.match_coarse(capabilities, "analyze_sales")
        assert "analyze:data" in matches

        matches = CapabilityMatcher.match_coarse(capabilities, "validate_data")
        assert "validate" in matches

    def test_capability_matcher_scoring(self):
        """Test capability scoring."""
        capabilities = [
            Capability(name="analyze:sales", confidence=0.9),
            Capability(name="analyze:data", confidence=0.7),
            Capability(name="generate:report", confidence=1.0),
        ]

        event = Event(
            event_type="analyze:sales",
            data={"test": "data"},
        )

        scores = CapabilityMatcher.score_match(capabilities, event)

        # Exact match should get highest score
        assert scores["analyze:sales"] == 0.9  # confidence * 1.0
        # Partial match gets reduced score
        assert scores["analyze:data"] == 0.7 * 0.8  # confidence * 0.8
        # No match gets 0
        assert scores["generate:report"] == 0.0


class TestMemoryStrategies:
    """Tests for memory strategies."""

    def test_default_strategy(self):
        """Test default memory strategy."""
        strategy = MemoryStrategy()

        assert strategy.short_term.enabled is True
        assert strategy.short_term.max_items == 100
        assert strategy.long_term.enabled is True
        assert strategy.persistent.enabled is True

    def test_analyst_strategy(self):
        """Test analyst-optimized strategy."""
        strategy = MemoryStrategy.analyst_strategy()

        assert strategy.short_term.max_items == 1000
        assert strategy.long_term.max_size_mb == 10240
        assert strategy.semantic.enabled is True

    def test_coordinator_strategy(self):
        """Test coordinator-optimized strategy."""
        strategy = MemoryStrategy.coordinator_strategy()

        assert strategy.short_term.max_items == 5000
        assert strategy.long_term.enabled is False
        assert strategy.episodic.enabled is True

    def test_minimal_strategy(self):
        """Test minimal memory strategy."""
        strategy = MemoryStrategy.minimal_strategy()

        assert strategy.short_term.max_items == 50
        assert strategy.long_term.enabled is False
        assert strategy.persistent.enabled is False


class TestAgentIntegration:
    """Integration tests for agents."""

    @pytest.mark.asyncio
    async def test_agent_with_custom_process(self):
        """Test agent with custom process method."""

        class CustomAgent(BaseAgent):
            agent_type = "custom"
            capabilities = ["custom:process"]

            async def process(self, event: Event) -> Result:
                # Simple processing
                data = {"received": event.data, "processed_by": self.agent_id}
                return Result(
                    success=True,
                    data=data,
                    next_capabilities=["next:step"],
                )

        agent = CustomAgent()
        event = Event(
            event_type="CustomData",
            data={"test": "value"},
        )

        result = await agent.process(event)

        assert result.success is True
        assert "received" in result.data
        assert result.next_capabilities == ["next:step"]

    @pytest.mark.asyncio
    async def test_agent_memory_operations(self):
        """Test agent memory operations."""
        with patch("weaver_ai.memory.core.aioredis.Redis") as mock_redis:
            mock_redis.return_value = AsyncMock()

            agent = BaseAgent(
                agent_type="memory_test",
                memory_strategy=MemoryStrategy(
                    short_term={"max_items": 10},
                    long_term={"enabled": True},
                ),
            )

            # Initialize memory
            from weaver_ai.memory import AgentMemory

            agent.memory = AgentMemory(
                strategy=agent.memory_strategy,
                agent_id=agent.agent_id,
            )

            # Store and recall
            await agent.memory.remember("test_key", "test_value", "short_term")
            results = await agent.memory.recall(query="test")

            assert agent.memory.usage.total_stores == 1
            assert len(results) > 0
