"""
Simplified workflow builder for easy multi-agent orchestration.

This module provides a fluent API for building agent workflows with
automatic type-based routing and minimal configuration.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from weaver_ai.agents import BaseAgent
from weaver_ai.agents.discovery import TypeBasedRouter
from weaver_ai.workflow import Workflow, WorkflowResult, WorkflowState


class Flow:
    """
    Simplified workflow builder that automatically handles agent routing.

    This class provides a fluent API for building multi-agent workflows
    with automatic type-based routing, parallel execution, and conditional logic.

    Example:
        flow = Flow("support")
        flow.chain(classify, route, respond)
        result = await flow.run("Help needed")
    """

    def __init__(self, name: str = "default", redis_url: str | None = None):
        """
        Initialize a new flow.

        Args:
            name: The name of the flow
            redis_url: Optional Redis URL for distributed execution
        """
        self.name = name
        self.redis_url = redis_url or "redis://localhost:6379"

        # Create underlying workflow
        self._workflow = Workflow(name, redis_url=self.redis_url)

        # Track agents in order
        self._agents: list[Callable] = []
        self._agent_instances: dict[str, BaseAgent] = {}

        # Type-based router for automatic connections
        self._router = TypeBasedRouter()

        # Configuration
        self._timeout = None
        self._observability = False
        self._intervention = False

    def add(self, agent_func: Callable) -> Flow:
        """
        Add a single agent to the flow.

        Args:
            agent_func: An @agent decorated function

        Returns:
            Self for chaining
        """
        if not hasattr(agent_func, "_agent_class"):
            raise ValueError(
                f"Function {agent_func.__name__} must be decorated with @agent"
            )

        self._agents.append(agent_func)

        # Add to underlying workflow
        agent_class = agent_func._agent_class
        agent_config = agent_func._agent_config

        self._workflow.add_agent(
            agent_class,
            instance_id=agent_func._agent_name,
            model=agent_config.get("model"),
            temperature=agent_config.get("temperature"),
            max_tokens=agent_config.get("max_tokens"),
            error_handling="retry" if agent_config.get("retry", 1) > 1 else "fail_fast",
            max_retries=agent_config.get("retry", 3),
        )

        return self

    def chain(self, *agents: Callable) -> Flow:
        """
        Chain multiple agents together with automatic type-based routing.

        The agents will be connected based on their input/output types.
        If types match (output of A matches input of B), they're automatically connected.

        Args:
            *agents: Multiple @agent decorated functions

        Returns:
            Self for chaining

        Example:
            flow.chain(parse, analyze, summarize)
            # Automatically connects: parse -> analyze -> summarize
        """
        for agent in agents:
            self.add(agent)

        # Set up automatic routing based on types
        if len(agents) > 1:
            for i in range(len(agents) - 1):
                current = agents[i]
                next_agent = agents[i + 1]

                # Check if types are compatible
                if hasattr(current, "_output_type") and hasattr(
                    next_agent, "_input_type"
                ):
                    # Skip TypeBasedRouter registration since we handle routing explicitly
                    # Type checking handled by decorated agents

                    # Skip TypeBasedRouter registration since we handle routing explicitly
                    pass

                    # Add explicit route for sequential chaining
                    self._workflow.add_route(
                        when=lambda result, idx=i: True,  # Always route in sequence
                        from_agent=current._agent_name,
                        to_agent=next_agent._agent_name,
                        priority=100 - i,  # Higher priority for earlier routes
                    )

        return self

    def parallel(self, *agents: Callable) -> Flow:
        """
        Run multiple agents in parallel.

        All agents will receive the same input and run concurrently.
        The results are collected and returned as a list.

        Args:
            *agents: Multiple @agent decorated functions

        Returns:
            Self for chaining

        Example:
            flow.parallel(check_inventory, check_price, check_shipping)
        """
        # Add all agents
        for agent in agents:
            self.add(agent)

        # Mark these agents for parallel execution
        # This is handled by the workflow's execution logic
        # We'll use a special routing pattern
        if len(agents) > 1:
            # Create a virtual "splitter" that sends to all agents
            for agent in agents:
                self._workflow.add_route(
                    when=lambda result: True,  # Always route
                    from_agent="__input__",  # Special marker for input
                    to_agent=agent._agent_name,
                    priority=50,  # Same priority for parallel
                )

        return self

    def pipe(self, agent_func: Callable) -> Flow:
        """
        Pipe data through an agent (alias for add).

        Args:
            agent_func: An @agent decorated function

        Returns:
            Self for chaining
        """
        return self.add(agent_func)

    def with_timeout(self, seconds: int) -> Flow:
        """
        Set a timeout for the entire workflow.

        Args:
            seconds: Timeout in seconds

        Returns:
            Self for chaining
        """
        self._timeout = seconds
        self._workflow = self._workflow.with_timeout(seconds)
        return self

    def with_observability(self, enabled: bool = True) -> Flow:
        """
        Enable observability for the workflow.

        Args:
            enabled: Whether to enable observability

        Returns:
            Self for chaining
        """
        self._observability = enabled
        self._workflow = self._workflow.with_observability(enabled)
        return self

    def with_intervention(self, enabled: bool = True) -> Flow:
        """
        Enable intervention for the workflow.

        Args:
            enabled: Whether to enable intervention

        Returns:
            Self for chaining
        """
        self._intervention = enabled
        self._workflow = self._workflow.with_intervention(enabled)
        return self

    async def run(self, input_data: Any) -> Any:
        """
        Run the flow with the given input.

        Args:
            input_data: The input data for the first agent

        Returns:
            The final output from the workflow
        """
        # Run the underlying workflow directly
        # The workflow will handle event creation internally
        result: WorkflowResult = await self._workflow.run(input_data)

        if result.state == WorkflowState.COMPLETED:
            return result.result
        elif result.state == WorkflowState.FAILED:
            raise RuntimeError(f"Workflow failed: {result.error}")
        else:
            raise RuntimeError(f"Workflow ended in unexpected state: {result.state}")

    def __or__(self, agent_func: Callable) -> Flow:
        """
        Pipe operator for chaining agents.

        Example:
            flow = Flow() | parse | analyze | respond
        """
        return self.add(agent_func)

    def __repr__(self) -> str:
        """String representation of the flow."""
        agents_str = " -> ".join(a.__name__ for a in self._agents)
        return f"Flow({self.name}): {agents_str}"


def flow(name: str = "default", redis_url: str | None = None) -> Flow:
    """
    Create a new flow with the given name.

    This is a convenience function for creating Flow instances.

    Args:
        name: The name of the flow
        redis_url: Optional Redis URL for distributed execution

    Returns:
        A new Flow instance

    Example:
        app = flow("my_app").chain(agent1, agent2, agent3)
        result = await app.run("input")
    """
    return Flow(name, redis_url)


class FlowBuilder:
    """
    Alternative flow builder with a more functional style.

    This provides an alternative API for users who prefer functional composition.
    """

    @staticmethod
    def sequence(*agents: Callable) -> Flow:
        """
        Create a sequential flow of agents.

        Args:
            *agents: Agents to run in sequence

        Returns:
            A configured Flow instance
        """
        f = Flow()
        return f.chain(*agents)

    @staticmethod
    def parallel(*agents: Callable) -> Flow:
        """
        Create a parallel flow of agents.

        Args:
            *agents: Agents to run in parallel

        Returns:
            A configured Flow instance
        """
        f = Flow()
        return f.parallel(*agents)

    @staticmethod
    def conditional(
        condition: Callable[[Any], bool], if_true: Callable, if_false: Callable
    ) -> Flow:
        """
        Create a conditional flow.

        Args:
            condition: Function to evaluate condition
            if_true: Agent to run if condition is true
            if_false: Agent to run if condition is false

        Returns:
            A configured Flow instance
        """
        f = Flow()
        f.add(if_true)
        f.add(if_false)

        # Add conditional routing
        f._workflow.add_route(
            when=condition,
            from_agent="__input__",
            to_agent=if_true._agent_name,
            priority=100,
        )

        f._workflow.add_route(
            when=lambda r: not condition(r),
            from_agent="__input__",
            to_agent=if_false._agent_name,
            priority=100,
        )

        return f
