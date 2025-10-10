"""Workflow orchestration with fluent API for agent composition."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from weaver_ai.agents import BaseAgent
from weaver_ai.agents.discovery import TypeBasedRouter
from weaver_ai.agents.error_handling import ErrorStrategy, RetryWithBackoff
from weaver_ai.events import Event
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
    agent_results: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """Configuration for an agent in a workflow."""

    agent_class: type[BaseAgent]
    instance_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    error_strategy: ErrorStrategy = Field(default_factory=RetryWithBackoff)
    model_name: str | None = None  # Specific model for this agent
    api_key: str | None = None  # Agent-specific API key (BYOK)
    model_settings: dict[str, Any] = Field(default_factory=dict)  # Model settings
    agent_settings: dict[str, Any] = Field(
        default_factory=dict
    )  # Additional agent configuration


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
        self.agents: list[AgentConfig] = []
        self.agent_instances: dict[str, BaseAgent] = {}

        # Routing configuration
        self.routes: list[RouteCondition] = []
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
        agent_class: type[BaseAgent],
        instance_id: str | None = None,
        error_handling: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **config,
    ) -> Workflow:
        """Add a single agent to the workflow.

        Args:
            agent_class: Agent class to instantiate
            instance_id: Optional instance ID for routing
            error_handling: Error handling strategy name
            model: Model name for this agent (e.g., 'gpt-4', 'claude-3-opus')
            api_key: API key for this agent's model (BYOK)
            temperature: Model temperature setting
            max_tokens: Maximum tokens for model responses
            **config: Additional agent configuration

        Returns:
            Self for chaining
        """
        if instance_id is None:
            instance_id = agent_class.__name__.lower()

        # Extract error strategy options from config
        error_options = {}
        if "max_retries" in config:
            error_options["max_retries"] = config.pop("max_retries")
        if "retry_delay" in config:
            error_options["retry_delay"] = config.pop("retry_delay")

        # Create error strategy
        if error_handling:
            error_strategy = self._create_error_strategy(
                error_handling, **error_options
            )
        else:
            error_strategy = self.default_error_strategy

        # Build model configuration
        model_settings = {}
        if temperature is not None:
            model_settings["temperature"] = temperature
        if max_tokens is not None:
            model_settings["max_tokens"] = max_tokens

        self.agents.append(
            AgentConfig(
                agent_class=agent_class,
                instance_id=instance_id,
                error_strategy=error_strategy,
                model_name=model,
                api_key=api_key,
                model_settings=model_settings,
                agent_settings=config,
            )
        )

        return self

    def add_agents(self, *agent_classes: type[BaseAgent]) -> Workflow:
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

        except TimeoutError:
            result.error = f"Workflow timed out after {self.timeout_seconds} seconds"
            result.state = WorkflowState.FAILED

        except IndexError:
            # Always re-raise IndexError for empty workflows
            raise

        except Exception as e:
            result.error = str(e)
            result.state = WorkflowState.FAILED

            # Check if any agent has fail_fast strategy
            for agent_config in self.agents:
                if (
                    hasattr(agent_config.error_strategy, "should_fail_workflow")
                    and agent_config.error_strategy.should_fail_workflow()
                ):
                    # Re-raise for fail-fast strategy
                    raise

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
        if not self.agents:
            raise IndexError("Cannot run workflow with no agents")

        for agent_config in self.agents:
            # Create agent instance
            agent = agent_config.agent_class(**agent_config.agent_settings)

            # Create model router for this specific agent if model is specified
            if agent_config.model_name:
                model_router = await self._create_agent_router(
                    model_name=agent_config.model_name,
                    api_key=agent_config.api_key,
                    config=agent_config.model_settings,
                )
            else:
                # Use shared/default router
                model_router = self.model_router

            # Initialize with connections
            await agent.initialize(redis_url=self.redis_url, model_router=model_router)

            # Store instance
            self.agent_instances[agent_config.instance_id] = agent

    async def _create_agent_router(
        self, model_name: str, api_key: str | None, config: dict[str, Any]
    ) -> ModelRouter:
        """Create a model router for a specific agent.

        Args:
            model_name: Name of the model to use
            api_key: Optional API key for the model (BYOK)
            config: Model configuration (temperature, max_tokens, etc.)

        Returns:
            Configured ModelRouter for the agent
        """
        import os

        from weaver_ai.models import ModelRouter
        from weaver_ai.models.anthropic_adapter import AnthropicAdapter
        from weaver_ai.models.mock import MockAdapter
        from weaver_ai.models.openai_adapter import OpenAIAdapter

        router = ModelRouter()

        # Determine model type and create appropriate adapter
        if "gpt" in model_name.lower():
            # OpenAI model
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if api_key:
                adapter = OpenAIAdapter(model=model_name)
                # Pass API key through environment for security
                os.environ["OPENAI_API_KEY"] = api_key
            else:
                # Fall back to mock if no API key
                adapter = MockAdapter(name=f"mock_{model_name}")
        elif "claude" in model_name.lower():
            # Anthropic model
            api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                adapter = AnthropicAdapter(model=model_name)
                # Pass API key through environment for security
                os.environ["ANTHROPIC_API_KEY"] = api_key
            else:
                # Fall back to mock if no API key
                adapter = MockAdapter(name=f"mock_{model_name}")
        elif model_name == "mock" or model_name.startswith("mock"):
            # Mock model (no API key needed)
            adapter = MockAdapter(name=model_name)
        else:
            # Unknown model type, fall back to mock
            adapter = MockAdapter(name=f"mock_{model_name}")

        # Register the adapter
        router.register(model_name, adapter)
        router.default_model = model_name

        return router

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
        first_agent_id = None
        if self.type_router:
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
                # Create event for agent - convert BaseModel to dict
                from pydantic import BaseModel

                event = Event(
                    event_type=current_data.__class__.__name__,
                    data=(
                        current_data.model_dump()
                        if isinstance(current_data, BaseModel)
                        else current_data
                    ),
                )

                # Process with the agent
                result = await self._process_with_error_handling(
                    agent, event, agent_config.error_strategy
                )

                if result is None:
                    break

                # Store agent result (but don't overwrite the agent instance)
                # Results are tracked in workflow result metadata

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

            except Exception:
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
        elif result:
            result_type = type(result)
        else:
            return None

        if self.type_router:
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
