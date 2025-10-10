"""Event models for type-safe agent communication.

This module defines the core data models for the event mesh system:
- AccessPolicy: Role and level-based access control
- EventMetadata: Event tracking and correlation
- Event: Type-safe event wrapper with Pydantic validation
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AccessPolicy(BaseModel):
    """Access control policy for events.

    Supports both role-based and level-based access control.
    Denied roles take precedence over allowed roles.

    Attributes:
        min_level: Minimum access level required (public, internal, confidential, secret)
        allowed_roles: List of roles that can access this event
        denied_roles: List of roles explicitly denied access
    """

    min_level: str = "public"
    allowed_roles: list[str] = Field(default_factory=list)
    denied_roles: list[str] = Field(default_factory=list)

    def can_access(self, agent_roles: list[str], agent_level: str) -> bool:
        """Check if an agent has access to this event.

        Args:
            agent_roles: Roles assigned to the agent
            agent_level: Access level of the agent

        Returns:
            True if agent has access, False otherwise
        """
        # Denied roles override everything
        if any(role in self.denied_roles for role in agent_roles):
            return False

        # If allowed roles specified, agent must have at least one
        if self.allowed_roles:
            return any(role in self.allowed_roles for role in agent_roles)

        # Check hierarchical access levels
        levels = ["public", "internal", "confidential", "secret"]
        if self.min_level in levels and agent_level in levels:
            return levels.index(agent_level) >= levels.index(self.min_level)

        return True


class EventMetadata(BaseModel):
    """Metadata for event tracking and correlation.

    Attributes:
        event_id: Unique identifier for this event
        timestamp: When the event was created
        source_agent: ID of agent that created the event
        parent_event_id: ID of event that triggered this one
        correlation_id: ID to correlate related events
        workflow_id: Workflow identifier for correlated events
        priority: Event priority (low, normal, high)
        metadata: Additional metadata as key-value pairs
    """

    event_id: str = Field(default_factory=lambda: uuid4().hex)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_agent: str | None = None
    parent_event_id: str | None = None
    correlation_id: str | None = None
    workflow_id: str | None = None
    priority: str = "normal"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Event(BaseModel):
    """Type-safe event wrapper with access control.

    Attributes:
        event_type: String identifier for the event type
        data: The actual event payload (as dict for serialization compatibility)
        metadata: Event tracking information
        access_policy: Access control rules
    """

    event_type: str
    data: dict[str, Any] | BaseModel
    metadata: EventMetadata = Field(default_factory=EventMetadata)
    access_policy: AccessPolicy = Field(default_factory=AccessPolicy)

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Override to ensure data is always serialized as dict."""
        result = super().model_dump(**kwargs)
        # Convert BaseModel data to dict if needed
        if isinstance(self.data, BaseModel):
            result["data"] = self.data.model_dump()
        return result

    def model_dump_json(self, **kwargs) -> str:
        """Override to ensure data is always serialized as dict."""
        # First convert to dict, then to JSON
        data_dict = self.model_dump(**kwargs)
        from pydantic import TypeAdapter

        return TypeAdapter(dict[str, Any]).dump_json(data_dict).decode()
