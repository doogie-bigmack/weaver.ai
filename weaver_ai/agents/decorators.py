"""Decorators for simple agent definition."""

from __future__ import annotations

from typing import Any, Callable

from .base import BaseAgent


def agent(
    agent_type: str | None = None,
    capabilities: list[str] | None = None,
    memory_strategy: str | None = None,
):
    """Decorator for creating agents with minimal boilerplate.
    
    Args:
        agent_type: Type of agent
        capabilities: List of capabilities
        memory_strategy: Predefined strategy name
        
    Returns:
        Decorated agent class
    """
    def decorator(cls):
        # Create new class inheriting from BaseAgent
        class DecoratedAgent(BaseAgent, cls):
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
                        kwargs["memory_strategy"] = MemoryStrategy.coordinator_strategy()
                    elif memory_strategy == "validator":
                        kwargs["memory_strategy"] = MemoryStrategy.validator_strategy()
                    elif memory_strategy == "minimal":
                        kwargs["memory_strategy"] = MemoryStrategy.minimal_strategy()
                        
                # Initialize BaseAgent
                BaseAgent.__init__(self, **kwargs)
                
                # Initialize original class if it has __init__ and it's not object's __init__
                if hasattr(cls, "__init__") and cls.__init__ != object.__init__:
                    cls.__init__(self, **kwargs)
        
        # Copy class attributes
        for attr in dir(cls):
            if not attr.startswith("_"):
                setattr(DecoratedAgent, attr, getattr(cls, attr))
                
        # Set class name and module
        DecoratedAgent.__name__ = cls.__name__
        DecoratedAgent.__module__ = cls.__module__
        
        return DecoratedAgent
        
    return decorator