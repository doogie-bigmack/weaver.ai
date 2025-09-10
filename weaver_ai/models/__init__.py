"""Model adapters for LLM integration and API models."""

from .anthropic_adapter import AnthropicAdapter
from .api import Citation, ErrorResponse, QueryRequest, QueryResponse, TelemetryEvent
from .base import ModelAdapter, ModelResponse
from .cached import CachedModelAdapter
from .connection_pool import HTTPConnectionPool
from .mock import MockAdapter
from .openai_adapter import OpenAIAdapter
from .openai_compatible import OpenAICompatibleAdapter
from .pooled_mock import PooledMockAdapter
from .router import ModelRouter

__all__ = [
    "ModelAdapter",
    "ModelResponse",
    "MockAdapter",
    "ModelRouter",
    "OpenAIAdapter",
    "OpenAICompatibleAdapter",
    "AnthropicAdapter",
    "CachedModelAdapter",
    "HTTPConnectionPool",
    "PooledMockAdapter",
    "QueryRequest",
    "QueryResponse",
    "Citation",
    "ErrorResponse",
    "TelemetryEvent",
]
