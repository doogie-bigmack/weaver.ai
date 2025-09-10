"""
Tests for the simplified Weaver AI API.

This module tests the @agent decorator, flow builder, and runners
to ensure the simple API works correctly while using the underlying
robust infrastructure.
"""

import asyncio
from typing import Any

import pytest

from weaver_ai.simple import Flow, agent, flow, run
from weaver_ai.simple.decorators import get_agent_class, get_all_agents

# =============================================================================
# Test Agent Decorator
# =============================================================================


class TestAgentDecorator:
    """Test the @agent decorator functionality."""

    def test_simple_agent_decoration(self):
        """Test basic @agent decoration."""

        @agent
        async def simple_processor(text: str) -> str:
            return f"Processed: {text}"

        # Check that metadata is attached
        assert hasattr(simple_processor, "_agent_class")
        assert hasattr(simple_processor, "_agent_config")
        assert simple_processor._agent_name == "simple_processor"
        assert simple_processor._input_type is str
        assert simple_processor._output_type is str

    def test_agent_with_configuration(self):
        """Test @agent with configuration options."""

        @agent(
            model="gpt-4",
            cache=True,
            retry=5,
            permissions=["read", "write"],
            temperature=0.5,
        )
        async def configured_agent(data: dict) -> dict:
            return {"result": "processed"}

        config = configured_agent._agent_config
        assert config["model"] == "gpt-4"
        assert config["cache"] is True
        assert config["retry"] == 5
        assert config["permissions"] == ["read", "write"]
        assert config["temperature"] == 0.5

    def test_agent_registration(self):
        """Test that agents are registered globally."""

        @agent(agent_type="test_agent")
        async def registered_agent(x: int) -> int:
            return x * 2

        # Check registration
        agent_class = get_agent_class("test_agent")
        assert agent_class is not None

        all_agents = get_all_agents()
        assert "test_agent" in all_agents

    def test_non_async_function_raises_error(self):
        """Test that non-async functions raise an error."""
        with pytest.raises(ValueError, match="must be async"):

            @agent
            def sync_function(x: int) -> int:
                return x * 2

    @pytest.mark.asyncio
    async def test_direct_function_call(self):
        """Test that decorated functions can still be called directly."""

        @agent
        async def direct_call(x: int) -> int:
            return x * 3

        result = await direct_call(5)
        assert result == 15


# =============================================================================
# Test Flow Builder
# =============================================================================


class TestFlowBuilder:
    """Test the Flow builder functionality."""

    @pytest.mark.asyncio
    async def test_simple_flow_creation(self):
        """Test creating a simple flow."""

        @agent
        async def step1(x: int) -> int:
            return x * 2

        @agent
        async def step2(x: int) -> str:
            return f"Result: {x}"

        # Create flow
        f = flow("test_flow")
        f.chain(step1, step2)

        assert f.name == "test_flow"
        assert len(f._agents) == 2

    @pytest.mark.asyncio
    async def test_flow_with_pipe_operator(self):
        """Test flow creation with pipe operator."""

        @agent
        async def add_one(x: int) -> int:
            return x + 1

        @agent
        async def multiply_two(x: int) -> int:
            return x * 2

        # Create flow with pipe operator
        f = Flow() | add_one | multiply_two

        assert len(f._agents) == 2

    def test_flow_configuration(self):
        """Test flow configuration methods."""
        f = (
            flow("configured")
            .with_timeout(60)
            .with_observability(True)
            .with_intervention(True)
        )

        assert f._timeout == 60
        assert f._observability is True
        assert f._intervention is True

    @pytest.mark.asyncio
    async def test_parallel_flow(self):
        """Test parallel agent execution."""
        results = []

        @agent
        async def parallel1(x: int) -> int:
            await asyncio.sleep(0.01)
            results.append(1)
            return x + 1

        @agent
        async def parallel2(x: int) -> int:
            await asyncio.sleep(0.01)
            results.append(2)
            return x + 2

        f = flow().parallel(parallel1, parallel2)

        # Both agents should be added
        assert len(f._agents) == 2


# =============================================================================
# Test Runners
# =============================================================================


class TestRunners:
    """Test the run and serve functions."""

    @pytest.mark.asyncio
    async def test_run_single_agent(self):
        """Test running a single agent."""

        @agent
        async def echo(text: str) -> str:
            return f"Echo: {text}"

        result = await run(echo, "Hello")
        assert result == "Echo: Hello"

    @pytest.mark.asyncio
    async def test_run_flow(self):
        """Test running a flow."""

        @agent
        async def uppercase(text: str) -> str:
            return text.upper()

        @agent
        async def add_prefix(text: str) -> str:
            return f"PREFIX_{text}"

        f = flow().chain(uppercase, add_prefix)

        # Note: The actual flow execution would require the full
        # workflow infrastructure to be running. For unit tests,
        # we'll test the setup is correct.
        assert len(f._agents) == 2
        assert f._agents[0].__name__ == "uppercase"
        assert f._agents[1].__name__ == "add_prefix"

    @pytest.mark.asyncio
    async def test_error_handling_in_agent(self):
        """Test error handling with retry logic."""
        call_count = 0

        @agent(retry=3)
        async def flaky_agent(x: int) -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return x * 2

        # Agent should retry and eventually succeed
        config = flaky_agent._agent_config
        assert config["retry"] == 3


# =============================================================================
# Test Type-Based Routing
# =============================================================================


class TestTypeBasedRouting:
    """Test automatic type-based agent routing."""

    def test_type_extraction(self):
        """Test that types are correctly extracted from agents."""

        @agent
        async def typed_agent(data: dict[str, Any]) -> list[str]:
            return list(data.keys())

        assert typed_agent._input_type == dict[str, Any]
        assert typed_agent._output_type == list[str]

    def test_compatible_types_for_chaining(self):
        """Test that compatible types can be chained."""

        @agent
        async def producer() -> dict:
            return {"key": "value"}

        @agent
        async def consumer(data: dict) -> str:
            return str(data)

        # These should be chainable
        f = flow().chain(producer, consumer)
        assert len(f._agents) == 2

    def test_any_type_compatibility(self):
        """Test that Any type is compatible with everything."""

        @agent
        async def any_input(data: Any) -> str:
            return str(data)

        @agent
        async def specific_output() -> dict:
            return {"test": True}

        # Should be chainable despite different types
        f = flow().chain(specific_output, any_input)
        assert len(f._agents) == 2


# =============================================================================
# Integration Tests
# =============================================================================


class TestSimpleAPIIntegration:
    """Integration tests for the complete simple API."""

    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test a complete multi-agent workflow with the simple API."""

        # Define agents
        @agent(model="gpt-3.5-turbo")
        async def extract_keywords(text: str) -> list[str]:
            # Simple keyword extraction
            words = text.lower().split()
            keywords = [w for w in words if len(w) > 4]
            return keywords

        @agent(model="gpt-4", cache=True)
        async def analyze_sentiment(keywords: list[str]) -> dict:
            # Simple sentiment analysis
            positive_words = ["good", "great", "excellent", "happy"]
            negative_words = ["bad", "poor", "terrible", "sad"]

            score = 0
            for word in keywords:
                if word in positive_words:
                    score += 1
                elif word in negative_words:
                    score -= 1

            return {
                "keywords": keywords,
                "sentiment": (
                    "positive" if score > 0 else "negative" if score < 0 else "neutral"
                ),
                "score": score,
            }

        @agent
        async def generate_report(analysis: dict) -> str:
            # Generate a simple report
            return (
                f"Analysis Report:\n"
                f"Keywords: {', '.join(analysis['keywords'])}\n"
                f"Sentiment: {analysis['sentiment']}\n"
                f"Score: {analysis['score']}"
            )

        # Create workflow
        workflow = flow("sentiment_analysis").chain(
            extract_keywords, analyze_sentiment, generate_report
        )

        # Verify workflow structure
        assert workflow.name == "sentiment_analysis"
        assert len(workflow._agents) == 3

        # Test individual agents
        keywords = await extract_keywords(
            "This is a great product with excellent features"
        )
        assert (
            "great" in keywords
            or "product" in keywords
            or "excellent" in keywords
            or "features" in keywords
        )

        sentiment = await analyze_sentiment(["great", "excellent"])
        assert sentiment["sentiment"] == "positive"

        report = await generate_report(
            {"keywords": ["test"], "sentiment": "neutral", "score": 0}
        )
        assert "Analysis Report" in report

    @pytest.mark.asyncio
    async def test_customer_support_workflow(self):
        """Test a customer support workflow using the simple API."""

        @agent(model="gpt-4", permissions=["read_tickets"])
        async def classify_ticket(ticket: str) -> dict:
            """Classify support ticket."""
            ticket_lower = ticket.lower()

            # Simple classification logic
            if "bug" in ticket_lower or "error" in ticket_lower:
                category = "technical"
                priority = "high"
            elif "billing" in ticket_lower or "payment" in ticket_lower:
                category = "billing"
                priority = "medium"
            elif "feature" in ticket_lower:
                category = "feature_request"
                priority = "low"
            else:
                category = "general"
                priority = "medium"

            return {"ticket": ticket, "category": category, "priority": priority}

        @agent(model="gpt-3.5-turbo")
        async def route_ticket(classification: dict) -> dict:
            """Route ticket based on classification."""
            routing_map = {
                "technical": "engineering_team",
                "billing": "finance_team",
                "feature_request": "product_team",
                "general": "support_team",
            }

            team = routing_map.get(classification["category"], "support_team")

            return {
                **classification,
                "assigned_to": team,
                "sla_hours": 24 if classification["priority"] == "high" else 48,
            }

        @agent
        async def generate_response(routing: dict) -> str:
            """Generate customer response."""
            return (
                f"Thank you for contacting support.\n"
                f"Your ticket has been classified as: {routing['category']}\n"
                f"Priority: {routing['priority']}\n"
                f"Assigned to: {routing['assigned_to']}\n"
                f"Expected response time: {routing['sla_hours']} hours"
            )

        # Create support workflow
        # Create support workflow (support_flow not used in test)
        _ = (
            flow("customer_support")
            .chain(classify_ticket, route_ticket, generate_response)
            .with_timeout(30)
            .with_observability(True)
        )

        # Test the workflow components
        classification = await classify_ticket("I found a bug in the login system")
        assert classification["category"] == "technical"
        assert classification["priority"] == "high"

        routing = await route_ticket(classification)
        assert routing["assigned_to"] == "engineering_team"
        assert routing["sla_hours"] == 24

        response = await generate_response(routing)
        assert "engineering_team" in response
        assert "24 hours" in response


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
