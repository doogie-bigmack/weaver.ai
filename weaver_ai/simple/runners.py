"""
Simple execution and serving utilities for Weaver AI flows.

This module provides easy-to-use functions for running flows and
serving them as HTTP APIs without dealing with the underlying complexity.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .flow import Flow


class SimpleRequest(BaseModel):
    """Simple request model for flow execution."""

    input: Any
    config: dict[str, Any] = {}


class SimpleResponse(BaseModel):
    """Simple response model for flow execution."""

    output: Any
    success: bool = True
    error: str | None = None


async def run(agent_or_flow: Callable | Flow, input_data: Any, **kwargs) -> Any:
    """
    Run an agent or flow with the given input.

    This function provides a simple way to execute agents or flows
    without dealing with the underlying complexity of events and envelopes.

    Args:
        agent_or_flow: Either an @agent decorated function or a Flow instance
        input_data: The input data to process
        **kwargs: Additional configuration options

    Returns:
        The output from the agent or flow

    Example:
        @agent
        async def process(text: str) -> str:
            return f"Processed: {text}"

        result = await run(process, "Hello")
        # Returns: "Processed: Hello"

        # Or with a flow:
        flow = Flow().chain(agent1, agent2)
        result = await run(flow, "input")
    """
    if isinstance(agent_or_flow, Flow):
        # Run the flow
        return await agent_or_flow.run(input_data)
    elif hasattr(agent_or_flow, "_agent_class"):
        # Run a single agent
        from pydantic import BaseModel, Field

        from weaver_ai.events import Event, EventMetadata

        # Create a simple wrapper for any data type
        class SimpleData(BaseModel):
            value: Any = Field(default=None)

        # Create agent instance
        agent_class = agent_or_flow._agent_class
        # agent_config = agent_or_flow._agent_config  # Available if needed

        # Create a minimal agent instance
        # Note: The agent_class already has func and config embedded
        agent = agent_class()

        # Wrap the input data if it's not already a BaseModel
        if isinstance(input_data, BaseModel):
            event_data = input_data
        else:
            event_data = SimpleData(value=input_data)

        # Create event with proper structure - convert BaseModel to dict
        event = Event(
            event_type=event_data.__class__.__name__,
            data=(
                event_data.model_dump()
                if isinstance(event_data, BaseModel)
                else event_data
            ),
            metadata=EventMetadata(event_id="simple_run", source_agent="simple_runner"),
        )

        # Process and return result
        return await agent.process(event)
    elif asyncio.iscoroutinefunction(agent_or_flow):
        # Direct async function call
        return await agent_or_flow(input_data)
    else:
        raise ValueError(
            "First argument must be an @agent decorated function or a Flow instance"
        )


def serve(
    agent_or_flow: Callable | Flow,
    port: int = 8000,
    host: str = "0.0.0.0",
    title: str = "Weaver AI Simple API",
    description: str = "Auto-generated API from Weaver AI agents",
    **kwargs,
) -> FastAPI:
    """
    Serve an agent or flow as an HTTP API.

    This function creates a FastAPI application that exposes the agent or flow
    as HTTP endpoints, handling all the complexity of request/response conversion.

    Args:
        agent_or_flow: Either an @agent decorated function or a Flow instance
        port: The port to serve on
        host: The host to bind to
        title: API title for documentation
        description: API description for documentation
        **kwargs: Additional FastAPI configuration

    Returns:
        The FastAPI application instance

    Example:
        @agent
        async def chatbot(message: str) -> str:
            return f"Response to: {message}"

        # Serve as API
        serve(chatbot, port=8000)
        # Now accessible at http://localhost:8000/process

        # Or serve a flow:
        flow = Flow().chain(agent1, agent2)
        serve(flow, port=8000)
    """
    # Create FastAPI app
    app = FastAPI(title=title, description=description, **kwargs)

    # Add health check
    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "weaver-ai-simple"}

    # Add main processing endpoint
    @app.post("/process", response_model=SimpleResponse)
    async def process(request: SimpleRequest):
        """Process input through the agent or flow."""
        try:
            result = await run(agent_or_flow, request.input)
            return SimpleResponse(output=result, success=True)
        except Exception as e:
            return SimpleResponse(output=None, success=False, error=str(e))

    # Add GET endpoint for simple queries
    @app.get("/process")
    async def process_get(input: str):
        """Process simple text input via GET request."""
        try:
            result = await run(agent_or_flow, input)
            return {"output": result, "success": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    # Add batch processing endpoint
    @app.post("/batch", response_model=list[SimpleResponse])
    async def batch_process(requests: list[SimpleRequest]):
        """Process multiple inputs in parallel."""
        tasks = [run(agent_or_flow, req.input) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses = []
        for result in results:
            if isinstance(result, Exception):
                responses.append(
                    SimpleResponse(output=None, success=False, error=str(result))
                )
            else:
                responses.append(SimpleResponse(output=result, success=True))

        return responses

    # Add metadata endpoint
    @app.get("/metadata")
    async def metadata():
        """Get metadata about the agent or flow."""
        if isinstance(agent_or_flow, Flow):
            return {
                "type": "flow",
                "name": agent_or_flow.name,
                "agents": [a.__name__ for a in agent_or_flow._agents],
            }
        elif hasattr(agent_or_flow, "_agent_config"):
            config = agent_or_flow._agent_config
            return {
                "type": "agent",
                "name": agent_or_flow.__name__,
                "model": config.get("model"),
                "cache": config.get("cache"),
                "retry": config.get("retry"),
            }
        else:
            return {"type": "unknown"}

    # Start the server if running as main
    if kwargs.get("start", True):
        import uvicorn

        uvicorn.run(app, host=host, port=port)

    return app


def create_handler(agent_or_flow: Callable | Flow) -> Callable[[Any], Any]:
    """
    Create a simple handler function from an agent or flow.

    This is useful for integrating with other frameworks or serverless platforms.

    Args:
        agent_or_flow: Either an @agent decorated function or a Flow instance

    Returns:
        An async handler function

    Example:
        handler = create_handler(my_agent)
        result = await handler("input")
    """

    async def handler(input_data: Any) -> Any:
        return await run(agent_or_flow, input_data)

    return handler


class SimpleOrchestrator:
    """
    Simple orchestrator for managing multiple flows.

    This class provides a way to manage and run multiple flows
    with shared configuration and resources.
    """

    def __init__(self, redis_url: str | None = None):
        """
        Initialize the orchestrator.

        Args:
            redis_url: Optional Redis URL for distributed execution
        """
        self.redis_url = redis_url
        self.flows: dict[str, Flow] = {}

    def register(self, name: str, flow: Flow) -> None:
        """
        Register a flow with the orchestrator.

        Args:
            name: The name to register the flow under
            flow: The Flow instance to register
        """
        self.flows[name] = flow

    async def run(self, flow_name: str, input_data: Any) -> Any:
        """
        Run a registered flow by name.

        Args:
            flow_name: The name of the flow to run
            input_data: The input data for the flow

        Returns:
            The output from the flow
        """
        if flow_name not in self.flows:
            raise ValueError(f"Flow '{flow_name}' not found")

        return await self.flows[flow_name].run(input_data)

    def serve_all(self, port: int = 8000, host: str = "0.0.0.0") -> FastAPI:
        """
        Serve all registered flows as a unified API.

        Args:
            port: The port to serve on
            host: The host to bind to

        Returns:
            The FastAPI application instance
        """
        app = FastAPI(
            title="Weaver AI Multi-Flow API",
            description="API serving multiple Weaver AI flows",
        )

        @app.get("/health")
        async def health():
            return {"status": "healthy", "flows": list(self.flows.keys())}

        @app.get("/flows")
        async def list_flows():
            """List all available flows."""
            return {
                "flows": [
                    {"name": name, "agents": [a.__name__ for a in flow._agents]}
                    for name, flow in self.flows.items()
                ]
            }

        @app.post("/run/{flow_name}")
        async def run_flow(flow_name: str, request: SimpleRequest):
            """Run a specific flow."""
            try:
                result = await self.run(flow_name, request.input)
                return SimpleResponse(output=result, success=True)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e)) from e
            except Exception as e:
                return SimpleResponse(output=None, success=False, error=str(e))

        return app
