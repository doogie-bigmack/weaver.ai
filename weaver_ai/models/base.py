"""Base model adapter interface."""

from typing import Protocol

from pydantic import BaseModel


class ModelResponse(BaseModel):
    """Response from a model."""

    text: str
    model: str
    tokens_used: int = 0
    # Optional fields for caching metadata
    cached: bool = False
    cache_key: str | None = None
    generation_time_ms: float | None = None


class ModelAdapter(Protocol):
    """Simple interface for LLM adapters."""

    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """Generate a response from the model."""
        ...
