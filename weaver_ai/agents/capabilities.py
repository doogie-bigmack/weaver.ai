"""Capability definitions and matching for agents."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from weaver_ai.events import Event


class Capability(BaseModel):
    """Rich capability definition for agents."""

    name: str  # e.g., "analyze:sales"
    description: str = ""
    input_schema: type[BaseModel] | None = None
    output_schema: type[BaseModel] | None = None
    constraints: dict[str, Any] = {}
    confidence: float = 1.0  # How well agent handles this (0-1)

    def matches(self, event_type: str) -> bool:
        """Check if capability matches event type.

        Args:
            event_type: Type of event

        Returns:
            True if matches
        """
        if ":" in self.name:
            action, subject = self.name.split(":", 1)
            return action in event_type.lower() or subject in event_type.lower()
        return self.name in event_type.lower()


class CapabilityMatcher:
    """Match events to agent capabilities."""

    @staticmethod
    def match_coarse(
        capabilities: list[str],
        event_type: str,
    ) -> list[str]:
        """Match on high-level capability.

        Args:
            capabilities: List of capability names
            event_type: Event type to match

        Returns:
            Matching capabilities
        """
        matches = []
        event_lower = event_type.lower()

        for cap in capabilities:
            if ":" in cap:
                # Split capability
                action, _ = cap.split(":", 1)
                if action in event_lower:
                    matches.append(cap)
            elif cap in event_lower:
                matches.append(cap)

        return matches

    @staticmethod
    def match_fine(
        capabilities: list[Capability],
        event: Event,
    ) -> list[Capability]:
        """Match on detailed capability with constraints.

        Args:
            capabilities: List of capability objects
            event: Event to match

        Returns:
            Matching capabilities
        """
        matches = []

        for cap in capabilities:
            # event.event_type is a class, so get its name
            event_type_name = event.event_type.__name__
            if cap.matches(event_type_name):
                # Check constraints if any
                if cap.constraints:
                    if CapabilityMatcher._check_constraints(cap.constraints, event):
                        matches.append(cap)
                else:
                    matches.append(cap)

        return matches

    @staticmethod
    def _check_constraints(
        constraints: dict[str, Any],
        event: Event,
    ) -> bool:
        """Check if event meets constraints.

        Args:
            constraints: Constraint dictionary
            event: Event to check

        Returns:
            True if all constraints met
        """
        # Simple constraint checking
        for key, value in constraints.items():
            if key == "max_size" and hasattr(event.data, "size"):
                if event.data.size > value:
                    return False
            elif key == "format" and hasattr(event.data, "format"):
                if event.data.format != value:
                    return False
            # Add more constraint types as needed

        return True

    @staticmethod
    def score_match(
        capabilities: list[str | Capability],
        event: Event,
    ) -> dict[str, float]:
        """Score how well capabilities match event.

        Args:
            capabilities: List of capabilities
            event: Event to score against

        Returns:
            Capability scores (0-1)
        """
        scores = {}

        for cap in capabilities:
            if isinstance(cap, str):
                cap_obj = Capability(name=cap)
            else:
                cap_obj = cap

            # Base score from confidence
            score = cap_obj.confidence

            # Adjust based on match quality
            # event.event_type is a class, so get its name
            event_type_name = event.event_type.__name__
            if cap_obj.matches(event_type_name):
                # Exact match gets full score (case-insensitive)
                if cap_obj.name.lower() == event_type_name.lower():
                    score *= 1.0
                # Partial match gets reduced score
                else:
                    score *= 0.8
            else:
                score = 0.0

            scores[cap_obj.name] = score

        return scores
