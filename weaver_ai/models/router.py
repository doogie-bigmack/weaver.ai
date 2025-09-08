"""Simple model router for selecting appropriate models."""

from .base import ModelAdapter, ModelResponse
from .mock import MockAdapter
from .pooled_mock import PooledMockAdapter


class ModelRouter:
    """Routes requests to appropriate models."""

    def __init__(self, use_connection_pooling: bool = True):
        self.models: dict[str, ModelAdapter] = {}
        self.default_model: str | None = None
        self.use_connection_pooling = use_connection_pooling

        # Use pooled mock adapter when connection pooling is enabled
        if use_connection_pooling:
            self.register("mock", PooledMockAdapter())
        else:
            self.register("mock", MockAdapter())
        self.default_model = "mock"

    def register(self, name: str, adapter: ModelAdapter) -> None:
        """Register a model adapter."""
        self.models[name] = adapter
        if not self.default_model:
            self.default_model = name

    async def generate(
        self, prompt: str, model: str | None = None, **kwargs
    ) -> ModelResponse:
        """Generate response using specified or default model."""
        model_name = model or self.default_model

        if not model_name or model_name not in self.models:
            raise ValueError(f"Model '{model_name}' not found")

        adapter = self.models[model_name]
        return await adapter.generate(prompt, **kwargs)

    def list_models(self) -> list[str]:
        """List available models."""
        return list(self.models.keys())
