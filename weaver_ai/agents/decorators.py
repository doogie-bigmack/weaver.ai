"""Decorators for simple agent definition."""

from __future__ import annotations

from typing import Type

from .base import BaseAgent


def agent(
    agent_type: str | None = None,
    capabilities: list[str] | None = None,
    memory_strategy: str | None = None,
) -> callable:
    """Decorator for creating agents with minimal boilerplate.

    Args:
        agent_type: Type of agent
        capabilities: List of capabilities
        memory_strategy: Predefined strategy name

    Returns:
        Decorated agent class
    """

    def decorator(cls: Type) -> Type[BaseAgent]:
        # If the class already inherits from BaseAgent, just modify it
        if issubclass(cls, BaseAgent):
            # Set class attributes from decorator
            if agent_type:
                cls.agent_type = agent_type
            if capabilities:
                cls.capabilities = capabilities

            # Store memory strategy to apply during init
            if memory_strategy:
                cls._decorator_memory_strategy = memory_strategy

            # Override __init__ to apply defaults
            original_init = cls.__init__

            def new_init(self, **kwargs):
                # Apply decorator defaults
                if agent_type and "agent_type" not in kwargs:
                    kwargs["agent_type"] = agent_type
                if capabilities and "capabilities" not in kwargs:
                    kwargs["capabilities"] = capabilities

                # Apply memory strategy
                if hasattr(cls, "_decorator_memory_strategy"):
                    from weaver_ai.memory import MemoryStrategy

                    strategy_name = cls._decorator_memory_strategy
                    if strategy_name == "analyst":
                        kwargs["memory_strategy"] = MemoryStrategy.analyst_strategy()
                    elif strategy_name == "coordinator":
                        kwargs["memory_strategy"] = (
                            MemoryStrategy.coordinator_strategy()
                        )
                    elif strategy_name == "validator":
                        kwargs["memory_strategy"] = MemoryStrategy.validator_strategy()
                    elif strategy_name == "minimal":
                        kwargs["memory_strategy"] = MemoryStrategy.minimal_strategy()

                original_init(self, **kwargs)

            cls.__init__ = new_init
            return cls

        # Create a new class that inherits from BaseAgent
        class DecoratedAgent(BaseAgent):
            def __init__(self, **kwargs):
                # Set defaults from decorator
                if agent_type:
                    kwargs.setdefault("agent_type", agent_type)
                if capabilities:
                    kwargs.setdefault("capabilities", capabilities)

                # Set memory strategy
                if memory_strategy:
                    from weaver_ai.memory import MemoryStrategy

                    if memory_strategy == "analyst":
                        kwargs["memory_strategy"] = MemoryStrategy.analyst_strategy()
                    elif memory_strategy == "coordinator":
                        kwargs["memory_strategy"] = (
                            MemoryStrategy.coordinator_strategy()
                        )
                    elif memory_strategy == "validator":
                        kwargs["memory_strategy"] = MemoryStrategy.validator_strategy()
                    elif memory_strategy == "minimal":
                        kwargs["memory_strategy"] = MemoryStrategy.minimal_strategy()

                # Initialize BaseAgent
                super().__init__(**kwargs)

        # Copy methods and attributes from the original class
        for attr_name in dir(cls):
            if not attr_name.startswith("_"):
                attr = getattr(cls, attr_name)
                # Only copy methods and class variables, not instance variables
                if callable(attr) or not callable(getattr(BaseAgent, attr_name, None)):
                    setattr(DecoratedAgent, attr_name, attr)

        # Set class name and module
        DecoratedAgent.__name__ = cls.__name__
        DecoratedAgent.__module__ = cls.__module__
        DecoratedAgent.__qualname__ = cls.__qualname__

        return DecoratedAgent

    return decorator
