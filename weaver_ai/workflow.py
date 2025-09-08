"""Workflow orchestration with fluent API for agent composition."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from weaver_ai.agents import BaseAgent
from weaver_ai.agents.discovery import TypeBasedRouter
from weaver_ai.agents.error_handling import ErrorStrategy, RetryWithBackoff
from weaver_ai.events import Event, EventMesh
from weaver_ai.models import ModelRouter
from weaver_ai.redis import RedisEventMesh


class WorkflowState(str, Enum):
    """Workflow execution states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowResult(BaseModel):
    """Result from workflow execution."""

    workflow_id: str
    state: WorkflowState
    result: Any = None
    error: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    agent_results: Dict[str, Any] = {}
    metrics: Dict[str, Any] = {}


class AgentConfig(BaseModel):
    """Configuration for an agent in a workflow."""

    agent_class: Type[BaseAgent]
    instance_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    error_strategy: ErrorStrategy = Field(default_factory=RetryWithBackoff)
    config: Dict[str, Any] = {}


class RouteCondition(BaseModel):
    """Conditional routing between agents."""

    condition: Callable[[Any], bool]
    from_agent: str
    to_agent: str
    priority: int = 0


class Workflow:
    """Fluent API for building and executing agent workflows.

    Example:
        workflow = (Workflow("analysis")
            .add_agents(Researcher, Analyst, Reporter)
            .with_observability(True)
            .with_error_handling("retry", max_retries=3))

        result = await workflow.run(input_data)
    """

    def __init__(self, name: str, redis_url: str = "redis://localhost:6379"):
        """Initialize a new workflow.

        Args:
            name: Workflow name
            redis_url: Redis connection URL
        """
        self.name = name
        self.workflow_id = f"{name}_{uuid.uuid4().hex[:8]}"
        self.redis_url = redis_url

        # Agent configuration
        self.agents: List[AgentConfig] = []
        self.agent_instances: Dict[str, BaseAgent] = {}

        # Routing configuration
        self.routes: List[RouteCondition] = []
        self.type_router: TypeBasedRouter | None = None

        # Workflow configuration
        self.observability_enabled = False
        self.intervention_enabled = False
        self.timeout_seconds: int | None = None
        self.default_error_strategy: ErrorStrategy = RetryWithBackoff()

        # Runtime state
        self.mesh: RedisEventMesh | None = None
        self.model_router: ModelRouter | None = None
        self.state = WorkflowState.PENDING

    def add_agent(
        self,
        agent_class: Type[BaseAgent],
        instance_id: str | None = None,
        error_handling: str | None = None,
        **config,
    ) -> Workflow:
        """Add a single agent to the workflow.

        Args:
            agent_class: Agent class to instantiate
            instance_id: Optional instance ID for routing
            error_handling: Error handling strategy name
            **config: Additional agent configuration

        Returns:
            Self for chaining
        """
        if instance_id is None:
            instance_id = agent_class.__name__.lower()

        # Create error strategy
        error_strategy = self._create_error_strategy(error_handling)

        self.agents.append(
            AgentConfig(
                agent_class=agent_class,
                instance_id=instance_id,
                error_strategy=error_strategy,
                config=config,
            )
        )

        return self

    def add_agents(self, *agent_classes: Type[BaseAgent]) -> Workflow:
        """Add multiple agents to the workflow.

        Args:
            *agent_classes: Agent classes to add

        Returns:
            Self for chaining
        """
        for agent_class in agent_classes:
            self.add_agent(agent_class)
        return self

    def add_route(
        self,
        when: Callable[[Any], bool],
        from_agent: str,
        to_agent: str,
        priority: int = 0,
    ) -> Workflow:
        """Add a conditional route between agents.

        Args:
            when: Condition function that returns True to activate route
            from_agent: Source agent instance ID
            to_agent: Target agent instance ID
            priority: Route priority (higher = higher priority)

        Returns:
            Self for chaining
        """
        self.routes.append(
            RouteCondition(
                condition=when,
                from_agent=from_agent,
                to_agent=to_agent,
                priority=priority,
            )
        )
        # Sort routes by priority
        self.routes.sort(key=lambda r: r.priority, reverse=True)
        return self

    def with_error_handling(
        self,
        strategy: str = "retry",
        max_retries: int = 3,
        backoff: str = "exponential",
        **options,
    ) -> Workflow:
        """Set default error handling for all agents.

        Args:
            strategy: Strategy name (retry, fail_fast, skip)
            max_retries: Maximum retry attempts
            backoff: Backoff strategy (exponential, linear, fixed)
            **options: Additional strategy options

        Returns:
            Self for chaining
        """
        self.default_error_strategy = self._create_error_strategy(
            strategy, max_retries=max_retries, backoff=backoff, **options
        )
        return self

    def with_observability(self, enabled: bool = True) -> Workflow:
        """Enable/disable workflow observability.

        Args:
            enabled: Whether to publish intermediate results

        Returns:
            Self for chaining
        """
        self.observability_enabled = enabled
        return self

    def with_intervention(self, enabled: bool = True) -> Workflow:
        """Enable/disable external intervention.

        Args:
            enabled: Whether to allow external agents to intervene

        Returns:
            Self for chaining
        """
        self.intervention_enabled = enabled
        return self

    def with_timeout(self, seconds: int) -> Workflow:
        """Set workflow execution timeout.

        Args:
            seconds: Timeout in seconds

        Returns:
            Self for chaining
        """
        self.timeout_seconds = seconds
        return self

    def discover_tools(self) -> Workflow:
        """Auto-discover and register MCP tools.

        Returns:
            Self for chaining
        """
        # This will be implemented when we add MCP discovery
        return self

    def with_model_router(self, router: ModelRouter) -> Workflow:
        """Set the model router for agents.

        Args:
            router: Model router instance

        Returns:
            Self for chaining
        """
        self.model_router = router
        return self

    async def run(self, input_data: Any) -> WorkflowResult:
        """Execute the workflow with input data.

        Args:
            input_data: Initial input for the workflow

        Returns:
            WorkflowResult with execution details
        """
        start_time = datetime.now(UTC)
        result = WorkflowResult(
            workflow_id=self.workflow_id,
            state=WorkflowState.RUNNING,
            start_time=start_time,
        )

        try:
            # Initialize connections
            await self._initialize()

            # Create and initialize agents
            await self._create_agents()

            # Setup type-based routing
            self._setup_routing()

            # Execute workflow
            if self.timeout_seconds:
                final_result = await asyncio.wait_for(
                    self._execute(input_data), timeout=self.timeout_seconds
                )
            else:
                final_result = await self._execute(input_data)

            result.result = final_result
            result.state = WorkflowState.COMPLETED

        except asyncio.TimeoutError:
            result.error = f"Workflow timed out after {self.timeout_seconds} seconds"
            result.state = WorkflowState.FAILED

        except Exception as e:
            result.error = str(e)
            result.state = WorkflowState.FAILED

        finally:
            result.end_time = datetime.now(UTC)
            await self._cleanup()

        return result

    async def _initialize(self):
        """Initialize workflow connections."""
        # Setup event mesh
        self.mesh = RedisEventMesh(self.redis_url)
        await self.mesh.connect()

        # Setup model router if not provided
        if self.model_router is None:
            from weaver_ai.models import ModelRouter

            self.model_router = ModelRouter()

    async def _create_agents(self):
        """Create and initialize agent instances."""
        for agent_config in self.agents:
            # Create agent instance
            agent = agent_config.agent_class(**agent_config.config)

            # Initialize with connections
            await agent.initialize(
                redis_url=self.redis_url, model_router=self.model_router
            )

            # Store instance
            self.agent_instances[agent_config.instance_id] = agent

    def _setup_routing(self):
        """Setup type-based routing."""
        from weaver_ai.agents.discovery import TypeBasedRouter

        # Create type router
        self.type_router = TypeBasedRouter()

        # Analyze agent types
        for agent_id, agent in self.agent_instances.items():
            self.type_router.register_agent(agent_id, agent)

    async def _execute(self, input_data: Any) -> Any:
        """Execute the workflow logic."""
        current_data = input_data
        current_agent_id = None

        # Find the first agent that can process the input
        first_agent_id = self.type_router.find_agent_for_type(type(input_data))
        if not first_agent_id:
            # Use the first registered agent as fallback
            first_agent_id = list(self.agent_instances.keys())[0]

        current_agent_id = first_agent_id

        # Process through the workflow
        max_iterations = 100  # Prevent infinite loops
        iteration = 0

        while current_agent_id and iteration < max_iterations:
            iteration += 1

            # Get current agent
            agent = self.agent_instances[current_agent_id]
            agent_config = self._get_agent_config(current_agent_id)

            # Publish observability event if enabled
            if self.observability_enabled:
                await self._publish_progress(current_agent_id, current_data)

            # Check for intervention if enabled
            if self.intervention_enabled:
                intervention = await self._check_intervention(
                    current_agent_id, current_data
                )
                if intervention:
                    current_agent_id = intervention
                    continue

            # Process with error handling
            try:
                # Create event for agent
                event = Event(data=current_data)

                # Process with the agent
                result = await self._process_with_error_handling(
                    agent, event, agent_config.error_strategy
                )

                if result is None:
                    break

                # Store agent result
                self.agent_instances[current_agent_id] = result

                # Find next agent
                next_agent_id = await self._find_next_agent(
                    current_agent_id, result, current_data
                )

                if next_agent_id:
                    current_data = result.data if hasattr(result, "data") else result
                    current_agent_id = next_agent_id
                else:
                    # No more agents, return final result
                    return result.data if hasattr(result, "data") else result

            except Exception as e:
                if agent_config.error_strategy.should_fail_workflow():
                    raise
                # Skip this agent and try to continue
                next_agent_id = await self._find_next_agent(
                    current_agent_id, None, current_data
                )
                if next_agent_id:
                    current_agent_id = next_agent_id
                else:
                    raise

        return current_data

    async def _process_with_error_handling(
        self, agent: BaseAgent, event: Event, strategy: ErrorStrategy
    ) -> Any:
        """Process event with error handling strategy."""
        return await strategy.execute(agent.process, event)

    async def _find_next_agent(
        self, current_agent_id: str, result: Any, data: Any
    ) -> str | None:
        """Find the next agent to process."""
        # Check manual routes first
        for route in self.routes:
            if route.from_agent == current_agent_id:
                if route.condition(result):
                    return route.to_agent

        # Fall back to type-based routing
        if result and hasattr(result, "data"):
            result_type = type(result.data)
        else:
            result_type = type(result) if result else None

        if result_type:
            return self.type_router.find_agent_for_type(result_type)

        return None

    async def _publish_progress(self, agent_id: str, data: Any):
        """Publish workflow progress for observability."""
        if self.mesh:
            progress_event = {
                "workflow_id": self.workflow_id,
                "agent_id": agent_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "data_type": type(data).__name__,
            }
            await self.mesh.publish("workflow.progress", progress_event)

    async def _check_intervention(self, agent_id: str, data: Any) -> str | None:
        """Check for external intervention requests."""
        # This will be implemented with intervention system
        return None

    def _get_agent_config(self, agent_id: str) -> AgentConfig:
        """Get configuration for an agent."""
        for config in self.agents:
            if config.instance_id == agent_id:
                return config
        raise ValueError(f"No configuration for agent {agent_id}")

    def _create_error_strategy(
        self, strategy_name: str | None, **options
    ) -> ErrorStrategy:
        """Create an error strategy by name."""
        if strategy_name is None:
            return self.default_error_strategy

        from weaver_ai.agents.error_handling import (
            FailFast,
            RetryWithBackoff,
            SkipOnError,
        )

        strategies = {
            "retry": RetryWithBackoff,
            "fail_fast": FailFast,
            "skip": SkipOnError,
        }

        strategy_class = strategies.get(strategy_name, RetryWithBackoff)
        return strategy_class(**options)

    async def _cleanup(self):
        """Cleanup workflow resources."""
        # Cleanup agents
        for agent in self.agent_instances.values():
            if hasattr(agent, "cleanup"):
                await agent.cleanup()

        # Close connections
        if self.mesh:
            await self.mesh.close()
