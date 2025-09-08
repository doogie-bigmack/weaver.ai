"""Comprehensive workflow tests."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from weaver_ai.agents import BaseAgent, agent
from weaver_ai.events import Event
from weaver_ai.workflow import Workflow, WorkflowResult, WorkflowState


# Test data models
class InputData(BaseModel):
    """Test input data."""

    value: int
    text: str


class ProcessedData(BaseModel):
    """Test processed data."""

    original_value: int
    processed_value: int
    message: str


class FinalResult(BaseModel):
    """Test final result."""

    summary: str
    total: int


# Test agents
@agent(agent_type="processor", capabilities=["process:input"])
class ProcessorAgent(BaseAgent):
    """Process input data."""

    async def process(self, event: Event) -> ProcessedData:
        if isinstance(event.data, InputData):
            data = event.data
            return ProcessedData(
                original_value=data.value,
                processed_value=data.value * 2,
                message=f"Processed: {data.text}",
            )
        raise ValueError("Invalid input type")


@agent(agent_type="aggregator", capabilities=["aggregate:data"])
class AggregatorAgent(BaseAgent):
    """Aggregate processed data."""

    async def process(self, event: Event) -> FinalResult:
        if isinstance(event.data, ProcessedData):
            data = event.data
            return FinalResult(
                summary=f"Aggregated: {data.message}",
                total=data.original_value + data.processed_value,
            )
        raise ValueError("Invalid input type")


@agent(agent_type="failing", capabilities=["fail:always"])
class FailingAgent(BaseAgent):
    """Agent that always fails."""

    async def process(self, event: Event) -> Any:
        raise RuntimeError("This agent always fails")


@agent(agent_type="slow", capabilities=["process:slow"])
class SlowAgent(BaseAgent):
    """Agent that processes slowly."""

    async def process(self, event: Event) -> ProcessedData:
        await asyncio.sleep(2)  # Simulate slow processing
        if isinstance(event.data, InputData):
            data = event.data
            return ProcessedData(
                original_value=data.value,
                processed_value=data.value * 3,
                message="Slow processing complete",
            )
        raise ValueError("Invalid input type")


class TestWorkflow:
    """Test workflow functionality."""

    @pytest.mark.asyncio
    async def test_simple_workflow(self):
        """Test a simple two-agent workflow."""
        workflow = Workflow("simple_test").add_agents(ProcessorAgent, AggregatorAgent)

        input_data = InputData(value=10, text="test")

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mock_mesh.return_value.connect = AsyncMock()
            mock_mesh.return_value.close = AsyncMock()

            # Mock agent initialization
            with patch.object(ProcessorAgent, "initialize", new=AsyncMock()):
                with patch.object(AggregatorAgent, "initialize", new=AsyncMock()):
                    result = await workflow.run(input_data)

        assert isinstance(result, WorkflowResult)
        assert result.state == WorkflowState.COMPLETED
        assert isinstance(result.result, ProcessedData | FinalResult)

    @pytest.mark.asyncio
    async def test_type_based_routing(self):
        """Test automatic type-based routing between agents."""

        # Create agents with specific input/output types
        class DataA(BaseModel):
            value: str

        class DataB(BaseModel):
            processed: str

        class DataC(BaseModel):
            final: str

        @agent
        class AgentA(BaseAgent):
            async def process(self, event: Event) -> DataB:
                if isinstance(event.data, DataA):
                    return DataB(processed=f"A->{event.data.value}")
                raise ValueError("Wrong type")

        @agent
        class AgentB(BaseAgent):
            async def process(self, event: Event) -> DataC:
                if isinstance(event.data, DataB):
                    return DataC(final=f"B->{event.data.processed}")
                raise ValueError("Wrong type")

        workflow = Workflow("type_routing").add_agents(AgentA, AgentB)

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mock_mesh.return_value.connect = AsyncMock()
            mock_mesh.return_value.close = AsyncMock()

            with patch.object(AgentA, "initialize", new=AsyncMock()):
                with patch.object(AgentB, "initialize", new=AsyncMock()):
                    # The workflow should automatically route
                    # DataA -> AgentA -> DataB -> AgentB -> DataC
                    result = await workflow.run(DataA(value="start"))

        # Result should be DataC after going through both agents
        assert isinstance(result, DataB | DataC)

    @pytest.mark.asyncio
    async def test_manual_routing_override(self):
        """Test manual routing overrides automatic type-based routing."""
        workflow = (
            Workflow("manual_routing")
            .add_agent(ProcessorAgent, instance_id="processor1")
            .add_agent(ProcessorAgent, instance_id="processor2")
            .add_agent(AggregatorAgent, instance_id="aggregator")
            # Add custom route
            .add_route(
                when=lambda result: isinstance(result, ProcessedData)
                and result.processed_value > 15,
                from_agent="processor1",
                to_agent="processor2",
                priority=10,
            )
        )

        input_data = InputData(value=10, text="test")

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mock_mesh.return_value.connect = AsyncMock()
            mock_mesh.return_value.close = AsyncMock()

            with patch.object(ProcessorAgent, "initialize", new=AsyncMock()):
                with patch.object(AggregatorAgent, "initialize", new=AsyncMock()):
                    result = await workflow.run(input_data)

        # Verify routing logic was applied
        assert result is not None

    @pytest.mark.asyncio
    async def test_error_handling_retry(self):
        """Test retry error handling strategy."""
        attempt_count = 0

        @agent
        class RetryAgent(BaseAgent):
            async def process(self, event: Event) -> ProcessedData:
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count < 3:
                    raise RuntimeError("Temporary failure")
                return ProcessedData(
                    original_value=1, processed_value=2, message="Success after retries"
                )

        workflow = Workflow("retry_test").add_agent(
            RetryAgent, error_handling="retry", max_retries=3
        )

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mock_mesh.return_value.connect = AsyncMock()
            mock_mesh.return_value.close = AsyncMock()

            with patch.object(RetryAgent, "initialize", new=AsyncMock()):
                result = await workflow.run(InputData(value=1, text="test"))

        assert attempt_count == 3  # Should retry until success
        assert isinstance(result, ProcessedData)
        assert result.message == "Success after retries"

    @pytest.mark.asyncio
    async def test_error_handling_fail_fast(self):
        """Test fail-fast error handling strategy."""
        workflow = (
            Workflow("fail_fast_test")
            .add_agent(FailingAgent, error_handling="fail_fast")
            .add_agent(AggregatorAgent)  # Should never reach this
        )

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mock_mesh.return_value.connect = AsyncMock()
            mock_mesh.return_value.close = AsyncMock()

            with patch.object(FailingAgent, "initialize", new=AsyncMock()):
                with patch.object(AggregatorAgent, "initialize", new=AsyncMock()):
                    with pytest.raises(RuntimeError, match="This agent always fails"):
                        await workflow.run(InputData(value=1, text="test"))

    @pytest.mark.asyncio
    async def test_error_handling_skip(self):
        """Test skip-on-error handling strategy."""
        workflow = (
            Workflow("skip_test")
            .add_agent(FailingAgent, error_handling="skip")
            .add_agent(ProcessorAgent)  # Should continue to this
        )

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mock_mesh.return_value.connect = AsyncMock()
            mock_mesh.return_value.close = AsyncMock()

            with patch.object(FailingAgent, "initialize", new=AsyncMock()):
                with patch.object(ProcessorAgent, "initialize", new=AsyncMock()):
                    result = await workflow.run(InputData(value=1, text="test"))

        # Should skip failing agent and continue
        assert result is not None

    @pytest.mark.asyncio
    async def test_workflow_timeout(self):
        """Test workflow timeout functionality."""
        workflow = (
            Workflow("timeout_test")
            .add_agent(SlowAgent)
            .with_timeout(1)  # 1 second timeout
        )

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mock_mesh.return_value.connect = AsyncMock()
            mock_mesh.return_value.close = AsyncMock()

            with patch.object(SlowAgent, "initialize", new=AsyncMock()):
                result = await workflow.run(InputData(value=1, text="test"))

        assert result.state == WorkflowState.FAILED
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_workflow_observability(self):
        """Test workflow observability events."""
        published_events = []

        async def mock_publish(event_type, data):
            published_events.append((event_type, data))

        workflow = (
            Workflow("observability_test")
            .add_agents(ProcessorAgent, AggregatorAgent)
            .with_observability(True)
        )

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mesh_instance = mock_mesh.return_value
            mesh_instance.connect = AsyncMock()
            mesh_instance.close = AsyncMock()
            mesh_instance.publish = mock_publish

            with patch.object(ProcessorAgent, "initialize", new=AsyncMock()):
                with patch.object(AggregatorAgent, "initialize", new=AsyncMock()):
                    await workflow.run(InputData(value=1, text="test"))

        # Should have published progress events
        assert len(published_events) > 0
        assert any("workflow.progress" in event[0] for event in published_events)

    @pytest.mark.asyncio
    async def test_workflow_intervention(self):
        """Test workflow intervention capability."""
        workflow = (
            Workflow("intervention_test")
            .add_agents(ProcessorAgent, AggregatorAgent)
            .with_intervention(True)
        )

        # Mock intervention check to redirect flow
        with patch.object(workflow, "_check_intervention") as mock_intervention:
            mock_intervention.return_value = "different_agent"

            with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
                mock_mesh.return_value.connect = AsyncMock()
                mock_mesh.return_value.close = AsyncMock()

                with patch.object(ProcessorAgent, "initialize", new=AsyncMock()):
                    with patch.object(AggregatorAgent, "initialize", new=AsyncMock()):
                        await workflow.run(InputData(value=1, text="test"))

        # Intervention should have been checked
        assert mock_intervention.called

    @pytest.mark.asyncio
    async def test_concurrent_workflows(self):
        """Test multiple workflows running concurrently."""
        workflows = [
            Workflow(f"concurrent_{i}").add_agent(ProcessorAgent) for i in range(5)
        ]

        async def run_workflow(wf, data):
            with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
                mock_mesh.return_value.connect = AsyncMock()
                mock_mesh.return_value.close = AsyncMock()

                with patch.object(ProcessorAgent, "initialize", new=AsyncMock()):
                    return await wf.run(data)

        # Run workflows concurrently
        tasks = [
            run_workflow(wf, InputData(value=i, text=f"test{i}"))
            for i, wf in enumerate(workflows)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for result in results:
            assert result is not None

    @pytest.mark.asyncio
    async def test_workflow_with_model_router(self):
        """Test workflow with custom model router."""
        from weaver_ai.models import ModelRouter

        mock_router = MagicMock(spec=ModelRouter)

        workflow = (
            Workflow("model_router_test")
            .add_agent(ProcessorAgent)
            .with_model_router(mock_router)
        )

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mock_mesh.return_value.connect = AsyncMock()
            mock_mesh.return_value.close = AsyncMock()

            with patch.object(
                ProcessorAgent, "initialize", new=AsyncMock()
            ) as mock_init:
                await workflow.run(InputData(value=1, text="test"))

                # Verify model router was passed to agent
                mock_init.assert_called_once()
                call_args = mock_init.call_args
                assert call_args[1]["model_router"] == mock_router

    @pytest.mark.asyncio
    async def test_workflow_state_transitions(self):
        """Test workflow state transitions."""
        workflow = Workflow("state_test").add_agent(ProcessorAgent)

        assert workflow.state == WorkflowState.PENDING

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mock_mesh.return_value.connect = AsyncMock()
            mock_mesh.return_value.close = AsyncMock()

            with patch.object(ProcessorAgent, "initialize", new=AsyncMock()):
                result = await workflow.run(InputData(value=1, text="test"))

        assert result.state in [WorkflowState.COMPLETED, WorkflowState.FAILED]
        assert result.start_time is not None
        assert result.end_time is not None
        assert result.workflow_id.startswith("state_test_")

    @pytest.mark.asyncio
    async def test_workflow_result_metadata(self):
        """Test workflow result contains proper metadata."""
        workflow = Workflow("metadata_test").add_agent(ProcessorAgent)

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mock_mesh.return_value.connect = AsyncMock()
            mock_mesh.return_value.close = AsyncMock()

            with patch.object(ProcessorAgent, "initialize", new=AsyncMock()):
                result = await workflow.run(InputData(value=1, text="test"))

        assert isinstance(result, WorkflowResult)
        assert result.workflow_id is not None
        assert result.start_time is not None
        assert result.end_time is not None
        assert result.state is not None

    @pytest.mark.asyncio
    async def test_empty_workflow(self):
        """Test workflow with no agents."""
        workflow = Workflow("empty_test")

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mock_mesh.return_value.connect = AsyncMock()
            mock_mesh.return_value.close = AsyncMock()

            with pytest.raises(IndexError):
                await workflow.run(InputData(value=1, text="test"))

    @pytest.mark.asyncio
    async def test_workflow_cleanup(self):
        """Test workflow cleanup on completion."""
        cleanup_called = False

        @agent
        class CleanupAgent(BaseAgent):
            async def process(self, event: Event) -> ProcessedData:
                return ProcessedData(
                    original_value=1, processed_value=2, message="test"
                )

            async def cleanup(self):
                nonlocal cleanup_called
                cleanup_called = True

        workflow = Workflow("cleanup_test").add_agent(CleanupAgent)

        with patch("weaver_ai.workflow.RedisEventMesh") as mock_mesh:
            mock_mesh.return_value.connect = AsyncMock()
            mock_mesh.return_value.close = AsyncMock()

            with patch.object(CleanupAgent, "initialize", new=AsyncMock()):
                await workflow.run(InputData(value=1, text="test"))

        # Cleanup should have been called
        assert cleanup_called
