"""
Simple API for Weaver AI - Developer-friendly interface

This module provides a simplified API that abstracts away the complexity
of the underlying A2A protocol, security, and telemetry systems while
maintaining all the power and robustness of the full framework.

Example:
    from weaver_ai.simple import agent, flow

    @agent
    async def process(text: str) -> str:
        return f"Processed: {text}"

    app = flow().add(process)
    result = await app.run("Hello")
"""

from .decorators import agent
from .flow import Flow, flow
from .runners import run, serve

__all__ = ["agent", "flow", "Flow", "run", "serve"]
