"""Agent discovery and type-based routing."""

from __future__ import annotations

import inspect
from typing import Any, get_type_hints

from pydantic import BaseModel

from weaver_ai.agents import BaseAgent


class TypeGraph(BaseModel):
    """Graph of agent input/output types for routing."""

    agents: dict[str, AgentTypeInfo] = {}
    type_to_agents: dict[str, list[str]] = {}
    connections: list[TypeConnection] = []


class AgentTypeInfo(BaseModel):
    """Type information for an agent."""

    agent_id: str
    input_types: list[str] = []
    output_types: list[str] = []
    capabilities: list[str] = []


class TypeConnection(BaseModel):
    """Connection between agents based on types."""

    from_agent: str
    to_agent: str
    shared_type: str
    confidence: float = 1.0


class TypeBasedRouter:
    """Automatic routing based on input/output types.

    This router analyzes agent process methods to determine:
    1. What types they accept as input
    2. What types they produce as output
    3. How agents can be connected based on type compatibility
    """

    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}
        self.type_graph = TypeGraph()

    def register_agent(self, agent_id: str, agent: BaseAgent):
        """Register an agent and analyze its types.

        Args:
            agent_id: Unique identifier for the agent
            agent: Agent instance to register
        """
        self.agents[agent_id] = agent

        # Analyze agent types
        type_info = self._analyze_agent_types(agent_id, agent)
        self.type_graph.agents[agent_id] = type_info

        # Update type mappings
        for input_type in type_info.input_types:
            if input_type not in self.type_graph.type_to_agents:
                self.type_graph.type_to_agents[input_type] = []
            self.type_graph.type_to_agents[input_type].append(agent_id)

        # Update connections
        self._update_connections()

    def find_agent_for_type(self, data_type: type) -> str | None:
        """Find an agent that can process the given type.

        Args:
            data_type: Type of data to process

        Returns:
            Agent ID that can process this type, or None
        """
        type_name = self._get_type_name(data_type)

        # Direct type match
        if type_name in self.type_graph.type_to_agents:
            agents = self.type_graph.type_to_agents[type_name]
            if agents:
                return agents[0]  # Return first matching agent

        # Check for compatible types (inheritance)
        for registered_type, agents in self.type_graph.type_to_agents.items():
            if self._is_compatible_type(data_type, registered_type):
                if agents:
                    return agents[0]

        # Check if any agent accepts generic 'Any' type
        if "Any" in self.type_graph.type_to_agents:
            agents = self.type_graph.type_to_agents["Any"]
            if agents:
                return agents[0]

        return None

    def find_next_agent(self, current_agent_id: str, output_type: type) -> str | None:
        """Find the next agent in the workflow based on output type.

        Args:
            current_agent_id: Current agent ID
            output_type: Type of output from current agent

        Returns:
            Next agent ID or None
        """
        type_name = self._get_type_name(output_type)

        # Find connections from current agent
        for connection in self.type_graph.connections:
            if connection.from_agent == current_agent_id:
                # Check if the connection matches the output type
                if connection.shared_type == type_name:
                    return connection.to_agent

        # Fall back to finding any agent that accepts this type
        # (excluding the current agent to avoid loops)
        next_agent = self.find_agent_for_type(output_type)
        if next_agent and next_agent != current_agent_id:
            return next_agent

        return None

    def validate_workflow_completeness(
        self,
        agents: list[str],
        input_type: type,
        expected_output_type: type | None = None,
    ) -> bool:
        """Validate that a workflow can execute completely.

        Args:
            agents: List of agent IDs in the workflow
            input_type: Initial input type
            expected_output_type: Expected final output type

        Returns:
            True if workflow is complete, False otherwise
        """
        if not agents:
            return False

        # Check if first agent can handle input
        first_agent = agents[0]
        first_info = self.type_graph.agents.get(first_agent)
        if not first_info:
            return False

        input_type_name = self._get_type_name(input_type)
        if input_type_name not in first_info.input_types:
            if "Any" not in first_info.input_types:
                return False

        # Check connections between agents
        for i in range(len(agents) - 1):
            current = agents[i]
            next_agent = agents[i + 1]

            # Check if there's a valid connection
            has_connection = False
            for connection in self.type_graph.connections:
                if (
                    connection.from_agent == current
                    and connection.to_agent == next_agent
                ):
                    has_connection = True
                    break

            if not has_connection:
                return False

        # Check expected output if provided
        if expected_output_type:
            last_agent = agents[-1]
            last_info = self.type_graph.agents.get(last_agent)
            if last_info:
                output_type_name = self._get_type_name(expected_output_type)
                if output_type_name not in last_info.output_types:
                    return False

        return True

    def get_workflow_path(
        self, input_type: type, output_type: type, max_length: int = 10
    ) -> list[str]:
        """Find a path of agents from input to output type.

        Args:
            input_type: Starting type
            output_type: Target type
            max_length: Maximum path length

        Returns:
            List of agent IDs forming a path, or empty list
        """
        input_name = self._get_type_name(input_type)
        output_name = self._get_type_name(output_type)

        # Find agents that accept input type
        start_agents = self.type_graph.type_to_agents.get(input_name, [])
        if not start_agents:
            return []

        # BFS to find path
        from collections import deque

        queue = deque([(agent, [agent]) for agent in start_agents])
        visited: set[str] = set()

        while queue and len(visited) < max_length * len(self.agents):
            current_agent, path = queue.popleft()

            if current_agent in visited:
                continue
            visited.add(current_agent)

            # Check if current agent produces output type
            agent_info = self.type_graph.agents[current_agent]
            if output_name in agent_info.output_types:
                return path

            # Find next agents
            for connection in self.type_graph.connections:
                if connection.from_agent == current_agent:
                    next_agent = connection.to_agent
                    if next_agent not in visited:
                        queue.append((next_agent, path + [next_agent]))

        return []

    def _analyze_agent_types(self, agent_id: str, agent: BaseAgent) -> AgentTypeInfo:
        """Analyze an agent's process method to determine types.

        Args:
            agent_id: Agent identifier
            agent: Agent instance

        Returns:
            Type information for the agent
        """
        type_info = AgentTypeInfo(agent_id=agent_id, capabilities=agent.capabilities)

        # Get the process method
        process_method = getattr(agent, "process", None)
        if not process_method:
            return type_info

        # Get type hints
        try:
            hints = get_type_hints(process_method)
        except Exception:
            # Fallback if type hints fail
            hints = {}

        # Analyze input types (parameters)
        sig = inspect.signature(process_method)
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # Get type from hints or annotation
            param_type = hints.get(param_name, param.annotation)
            if param_type != inspect.Parameter.empty:
                type_name = self._get_type_name(param_type)
                type_info.input_types.append(type_name)
            else:
                # Default to Any if no type specified
                type_info.input_types.append("Any")

        # Analyze output type (return annotation)
        return_type = hints.get("return", sig.return_annotation)
        if return_type != inspect.Signature.empty:
            # Handle async return types
            type_name = self._get_type_name(return_type)
            # Remove Awaitable wrapper if present
            if "Awaitable" in type_name:
                type_name = type_name.replace("Awaitable[", "").rstrip("]")
            type_info.output_types.append(type_name)
        else:
            type_info.output_types.append("Any")

        return type_info

    def _update_connections(self):
        """Update connections between agents based on type compatibility."""
        self.type_graph.connections.clear()

        # Find all possible connections
        for from_id, from_info in self.type_graph.agents.items():
            for to_id, to_info in self.type_graph.agents.items():
                if from_id == to_id:
                    continue

                # Check if output of 'from' matches input of 'to'
                for output_type in from_info.output_types:
                    if output_type in to_info.input_types:
                        connection = TypeConnection(
                            from_agent=from_id,
                            to_agent=to_id,
                            shared_type=output_type,
                            confidence=1.0,
                        )
                        self.type_graph.connections.append(connection)
                    elif "Any" in to_info.input_types:
                        # Agent accepts any type
                        connection = TypeConnection(
                            from_agent=from_id,
                            to_agent=to_id,
                            shared_type=output_type,
                            confidence=0.8,
                        )
                        self.type_graph.connections.append(connection)

    def _get_type_name(self, type_obj: type) -> str:
        """Get string name for a type object.

        Args:
            type_obj: Type object

        Returns:
            String representation of the type
        """
        if type_obj is None:
            return "None"

        # Handle special types
        if type_obj is Any:
            return "Any"

        # Get the name
        if hasattr(type_obj, "__name__"):
            return type_obj.__name__
        elif hasattr(type_obj, "__class__"):
            return type_obj.__class__.__name__
        else:
            return str(type_obj)

    def _is_compatible_type(self, data_type: type, registered_type: str) -> bool:
        """Check if a data type is compatible with a registered type.

        Args:
            data_type: Actual data type
            registered_type: Registered type name

        Returns:
            True if types are compatible
        """
        type_name = self._get_type_name(data_type)

        # Direct match
        if type_name == registered_type:
            return True

        # Check inheritance
        if hasattr(data_type, "__mro__"):
            for base in data_type.__mro__:
                if self._get_type_name(base) == registered_type:
                    return True

        # Check if registered type is Any
        if registered_type == "Any":
            return True

        return False
