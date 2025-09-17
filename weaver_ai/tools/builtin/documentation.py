"""Documentation tool for accessing library and API documentation."""

from __future__ import annotations

import time
from typing import Any, Dict

from ..base import Tool, ToolCapability, ToolExecutionContext, ToolResult


class DocumentationTool(Tool):
    """Tool for accessing documentation from various sources."""

    name: str = "documentation"
    description: str = "Access library and API documentation"
    capabilities: list[ToolCapability] = [
        ToolCapability.DOCUMENTATION,
        ToolCapability.ANALYSIS,
    ]
    required_scopes: list[str] = ["tool:documentation"]

    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "library": {
                "type": "string",
                "description": "Library or framework name",
            },
            "topic": {
                "type": "string",
                "description": "Specific topic to search for",
            },
            "version": {
                "type": "string",
                "description": "Library version (optional)",
            },
        },
        "required": ["library"],
    }

    output_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "library": {"type": "string"},
            "content": {"type": "string"},
            "examples": {
                "type": "array",
                "items": {"type": "string"},
            },
            "related_topics": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }

    async def execute(
        self,
        args: Dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        """Execute documentation search.

        Args:
            args: Documentation search arguments
            context: Execution context

        Returns:
            ToolResult with documentation content
        """
        start_time = time.time()

        try:
            library = args.get("library", "")
            topic = args.get("topic", "")
            version = args.get("version", "")

            if not library:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Library name is required",
                    execution_time=time.time() - start_time,
                    tool_name=self.name,
                    tool_version=self.version,
                )

            # This could integrate with context7 MCP server for real documentation
            # For now, return mock documentation
            content = f"""
# {library} Documentation

## Overview
This is the documentation for {library}{f' version {version}' if version else ''}.

## {topic if topic else 'Getting Started'}

{library} is a powerful library for building applications.

### Installation
```bash
pip install {library.lower().replace(' ', '-')}
```

### Basic Usage
```python
import {library.lower().replace(' ', '_')}

# Example code here
```

### Key Features
- Feature 1: Description
- Feature 2: Description
- Feature 3: Description
"""

            examples = [
                f"# Example 1: Basic {library} usage",
                f"# Example 2: Advanced {library} patterns",
                (
                    f"# Example 3: {library} with {topic}"
                    if topic
                    else f"# Example 3: {library} best practices"
                ),
            ]

            related_topics = [
                "Installation Guide",
                "API Reference",
                "Best Practices",
                "Troubleshooting",
            ]

            return ToolResult(
                success=True,
                data={
                    "library": library,
                    "content": content,
                    "examples": examples,
                    "related_topics": related_topics,
                },
                execution_time=time.time() - start_time,
                tool_name=self.name,
                tool_version=self.version,
                metadata={
                    "agent_id": context.agent_id,
                    "version_requested": version,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                execution_time=time.time() - start_time,
                tool_name=self.name,
                tool_version=self.version,
            )
