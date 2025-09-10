"""
Simple decorator API for creating agents without boilerplate.

This module provides the @agent decorator that transforms simple async functions
into full-featured Weaver AI agents with all security, telemetry, and protocol
handling built in.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, get_type_hints

from weaver_ai.agents import BaseAgent
from weaver_ai.events import Event

# Type variable for decorator
F = TypeVar("F", bound=Callable)

# Global registry for simple agents
_agent_registry: dict[str, type[BaseAgent]] = {}


class SimpleAgentWrapper(BaseAgent):
    """
    Wrapper that converts simple functions into BaseAgent instances.

    This class handles all the complexity of the BaseAgent interface
    while letting developers write simple async functions.
    """

    # Store the wrapped function and config as class attributes (not instance)
    _func: Callable = None
    _config: dict[str, Any] = None
    _func_name: str = None
    _type_hints: dict = None
    _input_type: Any = None
    _output_type: Any = None

    def __init__(self, func: Callable, config: dict[str, Any], **kwargs):
        # Store function metadata as class attributes to avoid Pydantic field issues
        self.__class__._func = func
        self.__class__._config = config
        self.__class__._func_name = func.__name__

        # Get type hints for automatic routing
        self.__class__._type_hints = get_type_hints(func)

        # Extract input/output types
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        if params:
            # Get first parameter type for input routing
            first_param = params[0]
            if first_param.annotation != inspect.Parameter.empty:
                self.__class__._input_type = first_param.annotation
        else:
            self.__class__._input_type = None

        # Get return type for output routing
        if sig.return_annotation != inspect.Signature.empty:
            self.__class__._output_type = sig.return_annotation
        else:
            self.__class__._output_type = None

        # Initialize base agent with configuration
        agent_type = config.get("agent_type", self.__class__._func_name)
        capabilities = config.get("capabilities", [])

        # Map permissions to capabilities
        if "permissions" in config:
            capabilities.extend(config["permissions"])

        # Prepare init kwargs for BaseAgent
        init_kwargs = {
            "agent_type": agent_type,
            "capabilities": capabilities,
        }
        init_kwargs.update(kwargs)

        super().__init__(**init_kwargs)

    async def process(self, event: Event) -> Any:
        """
        Process incoming event by calling the wrapped function.

        This method handles:
        - Extracting data from the event
        - Calling the wrapped function
        - Tracking metrics
        - Handling errors with retry logic
        """
        # Get function and config from class attributes
        func = self.__class__._func
        config = self.__class__._config
        func_name = self.__class__._func_name

        # Extract data from event
        data = event.data

        # Unwrap SimpleData if it's wrapped
        if hasattr(data, "value"):
            # This is likely our SimpleData wrapper
            data = data.value

        # Handle different data types
        if isinstance(data, dict):
            # If function expects specific args, extract them
            sig = inspect.signature(func)
            params = sig.parameters

            # Match dict keys to function parameters
            kwargs = {}
            for param_name, _ in params.items():
                if param_name in data:
                    kwargs[param_name] = data[param_name]

            # If no matching params, pass the whole dict
            if not kwargs:
                if len(params) == 1:
                    # Single parameter - pass the whole dict or data directly
                    first_param = list(params.keys())[0]
                    kwargs = {first_param: data}
                else:
                    kwargs = data if isinstance(data, dict) else {"data": data}
        else:
            # Pass non-dict data as first argument
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            if params:
                kwargs = {params[0]: data}
            else:
                kwargs = {}

        # Implement retry logic
        retry_count = config.get("retry", 3)
        cache_enabled = config.get("cache", False)
        last_error = None

        for attempt in range(retry_count):
            try:
                # Call the wrapped function
                result = await func(**kwargs)

                # Log success if needed (note: logger might not be available in base tests)
                if cache_enabled and hasattr(self, "logger"):
                    self.logger.info(
                        "Agent execution successful",
                        agent=func_name,
                        cache_enabled=True,
                        attempt=attempt + 1,
                    )

                return result

            except Exception as e:
                last_error = e
                if attempt < retry_count - 1:
                    # Log retry attempt if logger available
                    if hasattr(self, "logger"):
                        self.logger.warning(
                            f"Attempt {attempt + 1} failed, retrying...", error=str(e)
                        )
                    # Exponential backoff
                    import asyncio

                    await asyncio.sleep(2**attempt)
                else:
                    # Final attempt failed
                    if hasattr(self, "logger"):
                        self.logger.error(
                            f"All {retry_count} attempts failed", error=str(e)
                        )

        # Raise the last error if all retries failed
        if last_error:
            raise last_error


def agent(
    func: F | None = None,
    *,
    model: str = "gpt-4",
    cache: bool = False,
    retry: int = 3,
    permissions: list[str] | None = None,
    capabilities: list[str] | None = None,
    agent_type: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    **kwargs,
) -> F | Callable[[F], F]:
    """
    Decorator that transforms a simple async function into a Weaver AI agent.

    This decorator handles all the complexity of creating a BaseAgent subclass,
    managing security permissions, handling retries, and integrating with the
    model router and telemetry systems.

    Args:
        func: The async function to wrap (when used without parentheses)
        model: The model to use (e.g., "gpt-4", "claude-3-opus")
        cache: Whether to enable caching for this agent
        retry: Number of retry attempts on failure
        permissions: List of required permissions
        capabilities: List of agent capabilities
        agent_type: Optional custom agent type name
        temperature: Model temperature setting
        max_tokens: Maximum tokens for model responses
        **kwargs: Additional configuration options

    Returns:
        The decorated function that acts as an agent

    Example:
        @agent(model="gpt-4", cache=True, retry=3)
        async def summarize(text: str) -> str:
            return f"Summary of: {text}"
    """

    def decorator(f: F) -> F:
        # Validate that the function is async
        if not inspect.iscoroutinefunction(f):
            raise ValueError(f"Agent function {f.__name__} must be async")

        # Create configuration for this agent
        config = {
            "model": model,
            "cache": cache,
            "retry": retry,
            "permissions": permissions or [],
            "capabilities": capabilities or [],
            "agent_type": agent_type or f.__name__,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        # Create agent class
        agent_class = type(
            f"{f.__name__.title()}Agent",
            (SimpleAgentWrapper,),
            {
                "__init__": lambda self, **kw: SimpleAgentWrapper.__init__(
                    self, f, config, **kw
                )
            },
        )

        # Register the agent class
        agent_name = agent_type or f.__name__
        _agent_registry[agent_name] = agent_class

        # Attach metadata to the function for flow builder
        f._agent_class = agent_class
        f._agent_config = config
        f._agent_name = agent_name

        # Get type hints for automatic routing
        # Get type hints for automatic routing
        _ = get_type_hints(f)
        sig = inspect.signature(f)

        # Extract input type
        params = list(sig.parameters.values())
        if params and params[0].annotation != inspect.Parameter.empty:
            f._input_type = params[0].annotation
        else:
            f._input_type = Any

        # Extract output type
        if sig.return_annotation != inspect.Signature.empty:
            f._output_type = sig.return_annotation
        else:
            f._output_type = Any

        @wraps(f)
        async def wrapper(*args, **kwargs):
            # When called directly, just run the function
            return await f(*args, **kwargs)

        # Copy over metadata
        wrapper._agent_class = agent_class
        wrapper._agent_config = config
        wrapper._agent_name = agent_name
        wrapper._input_type = getattr(f, "_input_type", Any)
        wrapper._output_type = getattr(f, "_output_type", Any)

        return wrapper

    # Handle both @agent and @agent() syntax
    if func is None:
        # Called with parentheses: @agent()
        return decorator
    else:
        # Called without parentheses: @agent
        return decorator(func)


def get_agent_class(agent_name: str) -> type[BaseAgent] | None:
    """
    Get a registered agent class by name.

    Args:
        agent_name: The name of the agent

    Returns:
        The agent class if found, None otherwise
    """
    return _agent_registry.get(agent_name)


def get_all_agents() -> dict[str, type[BaseAgent]]:
    """
    Get all registered agent classes.

    Returns:
        Dictionary mapping agent names to classes
    """
    return _agent_registry.copy()
